# Copyright (c) 2026 Martial Systems LLC
"""Stage C: new P(sfha | hydro) train. HUC-10 CV, halo, isotonic. No FIM."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, brier_score_loss

from calumetmap.align import interior_mask, require_live_template, template_fingerprint, write_aligned
from calumetmap.calibrate import calibrate_leave_one_huc10, calibrate_oof_pooled
from calumetmap.codes import ZONE_FLOODWAY, ZONE_UNSHADED_X
from calumetmap.config import (
    C_HGB_L2,
    C_HGB_LEARNING_RATE,
    C_HGB_MAX_BINS,
    C_HGB_MAX_DEPTH,
    C_HGB_MAX_ITER,
    C_HGB_MIN_SAMPLES_LEAF,
    C_NEAR_STREAM_M,
    C_NON_SFHA_RATIO,
    C_RANDOM_SEED,
    CAL_PR_AUC_MAX_SHIFT,
    DIST_NODATA,
    FIRM_LIVE_MIN_HEIGHT,
    FIRM_LIVE_MIN_WIDTH,
    HAND_NODATA_RULE,
    HUC8,
    HYDRO_NODATA,
    LOCKED_TRANSFORM_SHA256,
    NLCD_NODATA,
    P_SFHA_CALIBRATED_NAME,
    P_SFHA_NODATA,
    P_SFHA_RAW_NAME,
    STAGE_C_FEATURES,
    TEMPLATE_KIND_NLCD,
)
from calumetmap.errors import GateError
from calumetmap.huc import load_huc
from calumetmap.huc10 import fetch_huc10_features, rasterize_huc10, save_huc10_geojson, train_test_halo
from calumetmap.report import build_stage_c_report, write_report
from calumetmap.stage_b import refuse_nora_hand_copy
from calumetmap.template import inspect_template

try:
    from calumetforge.gate import require_claims, require_huc, require_stage
except ImportError:  # pragma: no cover

    def require_claims(**kwargs):
        del kwargs

    def require_huc(**kwargs):
        del kwargs

    def require_stage(**kwargs):
        del kwargs


def _load_report(path: Path, stage: str) -> dict[str, Any]:
    if not path.is_file():
        raise GateError("Stage {0} report missing: {1}".format(stage, path))
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("stage") != stage or obj.get("gate") != "pass":
        raise GateError("Stage {0} report is not a passing artifact".format(stage))
    return obj


def hand_defined(hand: np.ndarray, inside: np.ndarray) -> np.ndarray:
    return inside & np.isfinite(hand) & (hand != HYDRO_NODATA)


def require_floodway_in_sfha(zone: np.ndarray, sfha: np.ndarray, inside: np.ndarray) -> None:
    floodway = (zone == ZONE_FLOODWAY) & inside
    if floodway.any() and not bool(np.all(sfha[floodway] == 1)):
        raise GateError("floodway cells missing from sfha==1")


def stratify_sample(
    *,
    pos: np.ndarray,
    neg: np.ndarray,
    unshaded_near: np.ndarray,
    ratio: float = C_NON_SFHA_RATIO,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    shape = pos.shape
    pos_i = np.flatnonzero(pos)
    n_pos = int(pos_i.size)
    if n_pos == 0:
        raise GateError("Stage C sample has no SFHA positives")
    n_neg_target = int(round(n_pos * ratio))
    neg_i = np.flatnonzero(neg)
    if neg_i.size == 0:
        raise GateError("Stage C sample has no non-SFHA cells")
    near_i = np.flatnonzero(unshaded_near & neg)
    n_near_take = min(int(near_i.size), max(n_neg_target // 2, 1)) if near_i.size else 0
    near_pick = (
        rng.choice(near_i, size=n_near_take, replace=False)
        if n_near_take
        else np.array([], dtype=np.intp)
    )
    other_pool = np.setdiff1d(neg_i, near_pick, assume_unique=False)
    n_other_take = min(int(other_pool.size), n_neg_target - n_near_take)
    other_pick = (
        rng.choice(other_pool, size=n_other_take, replace=False)
        if n_other_take
        else np.array([], dtype=np.intp)
    )
    idx = np.concatenate([pos_i, near_pick, other_pick])
    rows, cols = np.unravel_index(idx, shape)
    return rows.astype(np.int32, copy=False), cols.astype(np.int32, copy=False)


def gather_features(stack: dict[str, np.ndarray], rows: np.ndarray, cols: np.ndarray) -> np.ndarray:
    cols_feat = [stack[name][rows, cols] for name in STAGE_C_FEATURES]
    x = np.column_stack(cols_feat).astype(np.float32, copy=False)
    if x.shape[1] != len(STAGE_C_FEATURES):
        raise GateError("Stage C feature width mismatch")
    if "hsg" in STAGE_C_FEATURES:
        raise GateError("HSG is not an allowed Stage C feature")
    return x


def _fit_model(x: np.ndarray, y: np.ndarray, rng_seed: int) -> HistGradientBoostingClassifier:
    n_pos = int((y == 1).sum())
    n_neg = int((y == 0).sum())
    if n_pos == 0 or n_neg == 0:
        raise GateError("fold missing a class")
    leaf = min(C_HGB_MIN_SAMPLES_LEAF, max(10, int(x.shape[0] // 20)))
    w = np.where(y == 1, n_neg / n_pos, 1.0).astype(np.float64)
    clf = HistGradientBoostingClassifier(
        max_depth=C_HGB_MAX_DEPTH,
        max_iter=C_HGB_MAX_ITER,
        learning_rate=C_HGB_LEARNING_RATE,
        min_samples_leaf=leaf,
        l2_regularization=C_HGB_L2,
        max_bins=C_HGB_MAX_BINS,
        random_state=rng_seed,
    )
    clf.fit(x, y, sample_weight=w)
    return clf


def _metrics(y: np.ndarray, p: np.ndarray, pi: float) -> dict[str, float]:
    pr_auc = float(average_precision_score(y, p))
    brier = float(brier_score_loss(y, p))
    baseline = np.full(y.shape, pi, dtype=np.float64)
    pr_base = float(average_precision_score(y, baseline))
    brier_base = float(brier_score_loss(y, baseline))
    return {
        "pr_auc": pr_auc,
        "brier": brier,
        "pr_auc_baseline": pr_base,
        "brier_baseline": brier_base,
        "sfha_rate": float(pi),
    }


def run_stage_c(
    *,
    huc_path: Path,
    template_path: Path,
    interim_dir: Path,
    out_dir: Path,
    raw_dir: Path,
    stage_a_report_path: Path,
    stage_b_report_path: Path,
    get_json=None,
    huc10_features: list | None = None,
) -> dict:
    require_claims()
    refuse_nora_hand_copy(
        [huc_path, template_path, interim_dir, out_dir, stage_a_report_path, stage_b_report_path]
    )
    a_report = _load_report(stage_a_report_path, "A")
    b_report = _load_report(stage_b_report_path, "B")
    if not a_report.get("firm_unshaded_x_ok"):
        raise GateError("Stage C requires firm_unshaded_x_ok")
    if b_report.get("hand_nodata_filled_with_zero"):
        raise GateError("HAND nodata must not be filled with 0")
    if b_report.get("hand_nodata_rule") not in (None, HAND_NODATA_RULE):
        raise GateError("HAND nodata rule mismatch")
    if b_report.get("nora_hand_copied"):
        raise GateError("Stage C refuses a Nora HAND copy")
    if "hsg" in STAGE_C_FEATURES:
        raise GateError("HSG is not an allowed Stage C feature")
    huc = load_huc(huc_path)
    require_huc(huc8=huc.huc8, parent_huc=False)
    template = inspect_template(template_path, kind=TEMPLATE_KIND_NLCD)
    require_live_template(template)
    fp = template_fingerprint(template)
    live = template.width >= FIRM_LIVE_MIN_WIDTH and template.height >= FIRM_LIVE_MIN_HEIGHT
    a_fp = (a_report.get("template_fingerprint") or {}).get("transform_sha256")
    if a_fp and a_fp != fp["transform_sha256"]:
        raise GateError("Stage C template transform does not match Stage A")
    if a_fp == LOCKED_TRANSFORM_SHA256 and fp["transform_sha256"] != LOCKED_TRANSFORM_SHA256:
        raise GateError("live Stage C requires the locked template")
    require_stage(
        current_stage="B",
        target_stage="C",
        template_kind=TEMPLATE_KIND_NLCD,
        firm_unshaded_x_ok=True,
        stage_a_report=True,
        stage_b_report=True,
        thread_id="stage_c",
    )

    inside = interior_mask(template)
    with rasterio.open(interim_dir / "hand.tif") as src:
        hand = src.read(1).astype(np.float32)
    with rasterio.open(interim_dir / "dist_flowline.tif") as src:
        dist_fl = src.read(1).astype(np.float32)
    with rasterio.open(interim_dir / "dist_waterbody.tif") as src:
        dist_wb = src.read(1).astype(np.float32)
    with rasterio.open(interim_dir / "sfha.tif") as src:
        sfha = src.read(1)
    with rasterio.open(interim_dir / "slope.tif") as src:
        slope = src.read(1).astype(np.float32)
    with rasterio.open(interim_dir / "twi.tif") as src:
        twi = src.read(1).astype(np.float32)
    with rasterio.open(template.path) as src:
        nlcd = src.read(1).astype(np.float32)
        nlcd_nod = src.nodata if src.nodata is not None else NLCD_NODATA
    zone_path = interim_dir / "zone_class.tif"
    if zone_path.is_file():
        with rasterio.open(zone_path) as src:
            zone = src.read(1)
        require_floodway_in_sfha(zone, sfha, inside)
    else:
        zone = np.zeros(sfha.shape, dtype=np.uint8)

    defined = hand_defined(hand, inside)
    eligible = defined & ((sfha == 0) | (sfha == 1))
    n_hand_drop = int((inside & ~defined).sum())
    n_sfha = int(((sfha == 1) & eligible).sum())
    if n_sfha == 0:
        raise GateError("no SFHA positives after HAND-nodata drop")

    if huc10_features is None:
        huc10_features = fetch_huc10_features(get_json)
    save_huc10_geojson(huc10_features, raw_dir / "huc10_{0}.geojson".format(HUC8))
    huc10_info = rasterize_huc10(huc10_features, template, interim_dir / "huc10.tif")
    with rasterio.open(huc10_info["path"]) as src:
        huc10 = src.read(1)
    ids = [int(k) for k in huc10_info["legend"]]
    if len(ids) < 2:
        raise GateError("Stage C needs at least two HUC-10 blocks")

    stack = {
        "slope": slope,
        "twi": twi,
        "hand": hand,
        "dist_flowline": dist_fl,
        "dist_waterbody": dist_wb,
        "nlcd_impervious": np.where(nlcd == nlcd_nod, np.nan, nlcd),
    }
    if set(stack) != set(STAGE_C_FEATURES):
        raise GateError("Stage C stack keys != STAGE_C_FEATURES")

    unshaded_near = (
        (zone == ZONE_UNSHADED_X)
        & (
            ((dist_fl >= 0) & (dist_fl < C_NEAR_STREAM_M) & (dist_fl != DIST_NODATA))
            | ((dist_wb >= 0) & (dist_wb < C_NEAR_STREAM_M) & (dist_wb != DIST_NODATA))
        )
    )
    rng = np.random.default_rng(C_RANDOM_SEED)
    p_map = np.full(sfha.shape, P_SFHA_NODATA, dtype=np.float32)
    y_oof: list[np.ndarray] = []
    p_oof: list[np.ndarray] = []
    hand_oof: list[np.ndarray] = []
    n_train_pos = 0
    n_train_neg = 0
    n_halo = 0
    fold_rows: list[dict[str, Any]] = []

    for test_id in ids:
        if live:
            print("Stage C: HUC-10 {0}".format(huc10_info["legend"][str(test_id)]), flush=True)
        train_m, test_m, halo_m = train_test_halo(huc10, test_id, eligible)
        n_halo += int((halo_m & ~test_m).sum())
        if not test_m.any() or not train_m.any():
            continue
        pos = train_m & (sfha == 1)
        neg = train_m & (sfha == 0)
        tr, tc = stratify_sample(pos=pos, neg=neg, unshaded_near=unshaded_near, rng=rng)
        ytr = sfha[tr, tc].astype(np.uint8)
        xtr = gather_features(stack, tr, tc)
        finite = np.isfinite(xtr).all(axis=1)
        xtr, ytr = xtr[finite], ytr[finite]
        n_train_pos += int((ytr == 1).sum())
        n_train_neg += int((ytr == 0).sum())
        clf = _fit_model(xtr, ytr, C_RANDOM_SEED + test_id)
        er, ec = np.where(test_m)
        xte = gather_features(stack, er, ec)
        finite_te = np.isfinite(xte).all(axis=1)
        p = np.full(er.size, np.nan, dtype=np.float32)
        if finite_te.any():
            p[finite_te] = clf.predict_proba(xte[finite_te])[:, 1].astype(np.float32)
        ok = np.isfinite(p)
        p_map[er[ok], ec[ok]] = p[ok]
        y_oof.append(sfha[er[ok], ec[ok]].astype(np.uint8))
        p_oof.append(p[ok])
        hand_oof.append(hand[er[ok], ec[ok]])
        fold_rows.append(
            {
                "huc10": huc10_info["legend"][str(test_id)],
                "n_test": int(ok.sum()),
                "n_train_sampled": int(ytr.size),
            }
        )

    if not y_oof:
        raise GateError("Stage C produced no OOF predictions")
    y = np.concatenate(y_oof)
    p = np.concatenate(p_oof)
    hand_te = np.concatenate(hand_oof)
    pi = float((sfha[eligible] == 1).mean())
    metrics = _metrics(y, p, pi)
    hand_score = (-hand_te).astype(np.float64)
    hand_pr = float(average_precision_score(y, hand_score))
    if metrics["pr_auc"] <= metrics["pr_auc_baseline"]:
        raise GateError(
            "PR-AUC {0} is not above SFHA-rate baseline {1}".format(
                metrics["pr_auc"], metrics["pr_auc_baseline"]
            )
        )

    p_path = interim_dir / P_SFHA_RAW_NAME
    write_aligned(p_path, template, p_map, dtype="float32", nodata=P_SFHA_NODATA)
    with rasterio.open(p_path) as src:
        check = src.read(1)
    if not np.all(check[inside & ~defined] == P_SFHA_NODATA):
        raise GateError("p_sfha.tif filled HAND-nodata cells")

    valid_cal = defined & ((sfha == 0) | (sfha == 1))
    nested = calibrate_leave_one_huc10(p_map, sfha, huc10, valid_cal)
    nested_scored = valid_cal & (p_map != P_SFHA_NODATA) & (nested != P_SFHA_NODATA)
    nested_pr = float(
        average_precision_score(
            sfha[nested_scored].astype(np.uint8), nested[nested_scored].astype(np.float64)
        )
    ) if nested_scored.any() else float("nan")
    nested_shift = abs(nested_pr - metrics["pr_auc"]) if nested_scored.any() else float("inf")
    if nested_shift <= CAL_PR_AUC_MAX_SHIFT:
        p_cal = nested
        cal_method = "isotonic_leave_one_huc10_out"
    else:
        p_cal = calibrate_oof_pooled(p_map, sfha, valid_cal)
        cal_method = "isotonic_oof_pooled"
    if not np.all(p_cal[inside & ~defined] == P_SFHA_NODATA):
        raise GateError("calibrated raster filled HAND-nodata")
    cal_path = interim_dir / P_SFHA_CALIBRATED_NAME
    write_aligned(cal_path, template, p_cal, dtype="float32", nodata=P_SFHA_NODATA)
    with rasterio.open(p_path) as src:
        raw_after = src.read(1)
    if not np.array_equal(raw_after, check):
        raise GateError("isotonic overwrote p_sfha.tif")

    scored = valid_cal & (p_map != P_SFHA_NODATA) & (p_cal != P_SFHA_NODATA)
    y_cal = sfha[scored].astype(np.uint8)
    raw = p_map[scored].astype(np.float64)
    cal = p_cal[scored].astype(np.float64)
    m_cal = _metrics(y_cal, cal, pi)
    if abs(m_cal["pr_auc"] - metrics["pr_auc"]) > CAL_PR_AUC_MAX_SHIFT:
        raise GateError(
            "calibration moved PR-AUC too far: {0} -> {1}".format(
                metrics["pr_auc"], m_cal["pr_auc"]
            )
        )

    extra = {
        "template_fingerprint": fp,
        "features": list(STAGE_C_FEATURES),
        "model": "hist_gradient_boosting",
        "model_max_depth": C_HGB_MAX_DEPTH,
        "model_max_iter": C_HGB_MAX_ITER,
        "model_learning_rate": C_HGB_LEARNING_RATE,
        "upper_white_booster_copied": False,
        "hsg_in_model": False,
        "hand_nodata_rule": HAND_NODATA_RULE,
        "n_hand_nodata_excluded": n_hand_drop,
        "n_sfha_eligible": n_sfha,
        "n_oof": int(y.size),
        "n_train_pos_sampled": n_train_pos,
        "n_train_neg_sampled": n_train_neg,
        "non_sfha_ratio": C_NON_SFHA_RATIO,
        "n_huc10": huc10_info["n_huc10"],
        "huc10_codes": huc10_info["huc10_codes"],
        "n_halo_train_excluded": n_halo,
        "cv": "leave_one_huc10_out",
        "halo_pixels": 1,
        "pr_auc": metrics["pr_auc"],
        "pr_auc_baseline": metrics["pr_auc_baseline"],
        "brier": metrics["brier"],
        "brier_baseline": metrics["brier_baseline"],
        "sfha_rate_eligible": pi,
        "hand_negated_pr_auc": hand_pr,
        "model_minus_hand_pr_auc": metrics["pr_auc"] - hand_pr,
        "filename": P_SFHA_RAW_NAME,
        "p_sfha_path": str(p_path),
        "p_sfha_calibrated_path": str(cal_path),
        "filename_calibrated": P_SFHA_CALIBRATED_NAME,
        "raw_raster_kept": True,
        "method_calibrated": cal_method,
        "nested_isotonic_pr_auc": nested_pr,
        "nested_isotonic_pr_auc_shift": nested_shift,
        "n_scored_calibrated": int(y_cal.size),
        "oof_mean_p_raw": float(raw.mean()),
        "oof_mean_p_calibrated": float(cal.mean()),
        "pr_auc_calibrated": m_cal["pr_auc"],
        "brier_calibrated": m_cal["brier"],
        "probabilities_calibrated": True,
        "folds": fold_rows,
        "fim_started": False,
        "industrial_points_started": False,
        "nora_hand_copied": False,
    }
    report = build_stage_c_report(huc, template, extra=extra)
    require_stage(
        current_stage="C",
        target_stage="C",
        template_kind=TEMPLATE_KIND_NLCD,
        firm_unshaded_x_ok=True,
        stage_a_report=True,
        stage_b_report=True,
        probabilities_calibrated=True,
        thread_id="stage_c_complete",
    )
    write_report(out_dir, report)
    return report
