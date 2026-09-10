"""Explicit adapters; original scientific observations are never downloaded."""
from pathlib import Path
import json
import numpy as np
import pandas as pd


def geographic_groups(frame, k, seed=20260909):
    """Spherical k-means (12 starts); return zero-based labels and centroids."""
    lat = frame.latitude_deg.to_numpy(float)
    lon = frame.longitude_deg.to_numpy(float)
    if not np.isfinite(np.c_[lat, lon]).all() or np.any(abs(lat) > 90) or np.any(abs(lon) > 180):
        raise ValueError("Latitude/longitude must be finite degrees in [-90,90]/[-180,180]")
    lat, lon = np.deg2rad(lat), np.deg2rad(lon)
    xyz = np.c_[np.cos(lat)*np.cos(lon), np.cos(lat)*np.sin(lon), np.sin(lat)]
    if not 1 <= k <= len(np.unique(np.round(xyz, 12), axis=0)):
        raise ValueError("Group count exceeds distinct geographic positions")
    best = None
    for restart in range(12):
        rng = np.random.default_rng(seed+restart)
        centers = [xyz[rng.integers(len(xyz))]]
        for _ in range(1, k):
            distances = np.maximum(0, 1-xyz @ np.array(centers).T).min(axis=1)
            distances[distances < 1e-14] = 0
            if distances.sum() == 0:
                raise ValueError("Coordinates are numerically indistinguishable; use fewer groups")
            centers.append(xyz[rng.choice(len(xyz), p=distances/distances.sum())])
        centers = np.array(centers)
        previous = None
        for _ in range(100):
            dot = xyz @ centers.T
            labels = dot.argmax(axis=1)
            if previous is not None and np.array_equal(previous, labels):
                break
            previous = labels.copy()
            for c in range(k):
                members = xyz[labels == c]
                if len(members):
                    mean = members.mean(axis=0)
                    norm = np.linalg.norm(mean)
                    centers[c] = mean/norm if norm > 1e-12 else members[0]
                else:
                    centers[c] = xyz[np.argmin(dot.max(axis=1))]
        labels = (xyz @ centers.T).argmax(axis=1)
        if len(np.unique(labels)) != k:
            continue
        loss = float(np.maximum(0, 1-np.sum(xyz*centers[labels], axis=1)).sum())
        if best is None or loss < best[0]:
            best = loss, labels.copy(), centers.copy(), restart
    if best is None:
        raise ValueError("No nonempty spherical partition found; use fewer groups")
    loss, labels, centers, restart = best
    lat = np.rad2deg(np.arcsin(np.clip(centers[:, 2], -1, 1)))
    lon = np.rad2deg(np.arctan2(centers[:, 1], centers[:, 0]))
    order = np.lexsort((lat, lon))
    inverse = np.empty(k, int)
    inverse[order] = np.arange(k)
    return inverse[labels], dict(method="spherical_kmeans", seed=seed+restart,
        starts=12, loss=loss, centroids_latitude_longitude=np.c_[lat[order], lon[order]].tolist(),
        scope="Fitted to the supplied record, not tectonic-plate identities")


def ordered_groups(values, k):
    """Exact contiguous partition minimizing sum_g (n_g-N/K)^2.

    O(K M^2) time and O(K M) storage for M distinct mark values.
    Equal values are never split. Boundaries can be frozen for new observations.
    """
    values = np.asarray(values, dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Ordered marks must be finite")
    unique, counts = np.unique(values, return_counts=True)
    m = len(unique)
    if not 1 <= k <= m:
        raise ValueError("Group count must not exceed distinct ordered values")
    prefix = np.r_[0, np.cumsum(counts)]
    target = len(values)/k
    dp = np.full((k+1, m+1), np.inf)
    back = np.full((k+1, m+1), -1, int)
    dp[0, 0] = 0
    for groups in range(1, k+1):
        for end in range(groups, m+1):
            starts = np.arange(groups-1, end)
            options = dp[groups-1, starts]+(prefix[end]-prefix[starts]-target)**2
            at = int(np.argmin(options))
            dp[groups, end], back[groups, end] = options[at], starts[at]
    bounds, end = [m], m
    for groups in range(k, 0, -1):
        end = int(back[groups, end])
        bounds.append(end)
    bounds = bounds[::-1]
    # Use the first value of each new band as an inclusive lower boundary.
    # This avoids midpoint overflow and works for adjacent floating values.
    cuts = unique[np.array(bounds[1:-1], dtype=int)]
    labels = np.searchsorted(cuts, values, side="right")
    return labels, dict(method="contiguous_count_balance_dp", counts_sse=float(dp[k, m]),
        lower_inclusive_boundaries=cuts.tolist(), observed_min=float(unique[0]),
        observed_max=float(unique[-1]), distinct_values=m)


def import_csv(source, kind, time_column, category_column, time_unit):
    """Normalize arbitrary long CSV or USGS CSV to a local event table."""
    frame = pd.read_csv(source)
    if kind == "usgs":
        utc = pd.to_datetime(frame[time_column], utc=True, errors="raise")
        origin = utc.min()
        result = pd.DataFrame(dict(time_seconds=(utc-origin).dt.total_seconds(),
            latitude_deg=frame.latitude, longitude_deg=frame.longitude))
        meta = dict(time_origin_utc=origin.isoformat(), time_scale="UTC", adapter="USGS CSV")
    else:
        # Preserve string identities such as "001" exactly.
        frame = pd.read_csv(source, dtype={category_column: str}, keep_default_na=False)
        result = pd.DataFrame(dict(time_seconds=pd.to_numeric(frame[time_column])/time_unit,
                                  category=frame[category_column]))
        meta = dict(adapter="long CSV", source_units_per_second=time_unit)
    result.insert(0, "event_id", np.arange(1, len(result)+1))
    return result.sort_values("time_seconds", kind="stable"), meta


def import_nicer(source, pi_min=20, pi_max=1500):
    """Read a local NICER event FITS file and preserve GTIs in the same clock."""
    try:
        from astropy.io import fits
    except ImportError as exc:
        raise ValueError("Install the fits extra: pip install '.[fits]'") from exc
    with fits.open(source, memmap=False) as hdus:
        event_hdu = hdus["EVENTS"]
        gti_hdu = hdus["GTI"]
        for hdu in [event_hdu, gti_hdu]:
            if hdu.header.get("TIMEUNIT", "s").strip() != "s":
                raise ValueError("This NICER adapter requires second-based TIMEUNIT")
        # TIMEZERO may differ across extensions; use a common native clock.
        t = np.asarray(event_hdu.data["TIME"], float)+float(event_hdu.header.get("TIMEZERO", 0))
        gzero = float(gti_hdu.header.get("TIMEZERO", 0))
        start = np.asarray(gti_hdu.data["START"], float)+gzero
        stop = np.asarray(gti_hdu.data["STOP"], float)+gzero
        origin = float(start.min())
        t, start, stop = t-origin, start-origin, stop-origin
        pi = np.asarray(event_hdu.data["PI"], float)
        included = np.zeros(len(t), bool)
        for a, b in zip(start, stop):
            included |= (t >= a) & (t < b)
        included &= (pi >= pi_min) & (pi <= pi_max)
        events = pd.DataFrame(dict(event_id=np.flatnonzero(included)+1,
            time_seconds=t[included], ordered_mark=pi[included]))
        metadata = dict(adapter="NICER EVENTS/GTI", original_events=len(t),
            included_events=int(included.sum()), pi_inclusive_range=[pi_min, pi_max],
            native_clock_origin=origin, timesys=event_hdu.header.get("TIMESYS"),
            mjdrefi=event_hdu.header.get("MJDREFI"), mjdreff=event_hdu.header.get("MJDREFF"),
            limitation="PI/GTI filtering and band quantization are not invertible to all raw photons")
    return events.sort_values("time_seconds", kind="stable"), pd.DataFrame(dict(start_seconds=start, stop_seconds=stop)), metadata
