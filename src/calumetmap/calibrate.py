# Copyright (c) 2026 Martial Systems LLC
"""Isotonic calibration of OOF P(sfha | hydro) on the same HUC-10 cuts."""

from __future__ import annotations

import numpy as np
from sklearn.isotonic import IsotonicRegression

from calumetmap.config import P_SFHA_NODATA
from calumetmap.errors import GateError


def calibrate_leave_one_huc10(
    p_raw: np.ndarray,
    y: np.ndarray,
    huc10: np.ndarray,
    valid: np.ndarray,
) -> np.ndarray:
    """Fit isotonic on other HUC-10s' OOF (p, y); apply to the held-out HUC-10."""
    p_cal = np.full(p_raw.shape, P_SFHA_NODATA, dtype=np.float32)
    scored = valid & (p_raw != P_SFHA_NODATA) & np.isfinite(p_raw)
    ids = [int(i) for i in np.unique(huc10[scored]) if int(i) > 0]
    if len(ids) < 2:
        raise GateError("isotonic calibration needs at least two HUC-10 blocks")
    for k in ids:
        train = scored & (huc10 != k)
        test = scored & (huc10 == k)
        if int(train.sum()) < 4 or not test.any():
            continue
        iso = IsotonicRegression(
            y_min=0.0, y_max=1.0, increasing=True, out_of_bounds="clip"
        )
        iso.fit(p_raw[train].astype(np.float64), y[train].astype(np.float64))
        p_cal[test] = iso.predict(p_raw[test].astype(np.float64)).astype(np.float32)
    if not np.any(p_cal != P_SFHA_NODATA):
        raise GateError("isotonic calibration wrote no cells")
    return p_cal


def calibrate_oof_pooled(
    p_raw: np.ndarray,
    y: np.ndarray,
    valid: np.ndarray,
) -> np.ndarray:
    """One increasing map on OOF (p, y). Preserves rank; does not refit per HUC-10."""
    p_cal = np.full(p_raw.shape, P_SFHA_NODATA, dtype=np.float32)
    scored = valid & (p_raw != P_SFHA_NODATA) & np.isfinite(p_raw)
    if int(scored.sum()) < 4:
        raise GateError("isotonic calibration needs scored OOF cells")
    iso = IsotonicRegression(
        y_min=0.0, y_max=1.0, increasing=True, out_of_bounds="clip"
    )
    iso.fit(p_raw[scored].astype(np.float64), y[scored].astype(np.float64))
    p_cal[scored] = iso.predict(p_raw[scored].astype(np.float64)).astype(np.float32)
    return p_cal
