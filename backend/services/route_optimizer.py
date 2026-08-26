"""
Route Optimizer
===============
Clusters verified POIs into geographic daily zones using K-Means,
then sorts each zone with a nearest-neighbour heuristic to minimise
backtracking during the day.
"""
import math
from typing import Dict, List

# Business rule: cap how many of certain categories can land on a single day.
# "coffee" (chilling) ≤ 3/day, "food" (foodie) ≤ 5/day; other categories are
# only bounded by the user's max-stops-per-day setting.
DAILY_CATEGORY_CAPS = {"chilling": 3, "foodie": 5}


class RouteOptimizer:
    """
    K-Means based route planner.

    cluster_pois_by_day()  – main entry; requires lat/lng on each POI
    distribute_evenly()    – fallback when no coordinates are available
    """

    def cluster_pois_by_day(
        self,
        pois: List[Dict],
        num_days: int,
        max_per_day: int = 5,
        anchor: "tuple | None" = None,
    ) -> List[List[Dict]]:
        """
        Cluster geocoded POIs into ``num_days`` daily zones.

        Args:
            pois:        POI dicts that each have ``lat`` and ``lng``.
            num_days:    Number of travel days.
            max_per_day: Hard cap on stops per day.

        Returns:
            List[List[POI]] – one inner list per day, each sorted
            by nearest-neighbour visiting order.
        """
        from collections import defaultdict

        import numpy as np
        from sklearn.cluster import KMeans

        # Safety: only cluster what has coordinates
        geo = [p for p in pois if p.get("lat") and p.get("lng")]
        if not geo:
            return self.distribute_evenly(pois, num_days, max_per_day)

        k = min(num_days, len(geo))
        coords = np.array([[p["lat"], p["lng"]] for p in geo])

        km = KMeans(n_clusters=k, random_state=42, n_init=10, max_iter=300)
        km.fit(coords)
        centroids = km.cluster_centers_

        # ── Category-diversity constraint ────────────────────────────────
        # Pure K-Means clusters by geography, which can pile every café into
        # one day. We instead assign each POI to its *nearest* day-centroid,
        # but cap how many of any one category (foodie/chilling/photography…)
        # can land on a single day — so each day gets a balanced mix while
        # still respecting geography as the primary signal.
        cat_counts: Dict[str, int] = defaultdict(int)
        for p in geo:
            cat_counts[(p.get("category") or "other").lower()] += 1
        # Explicit business caps for coffee/food; everything else just follows
        # the overall max-stops-per-day (no tighter per-category limit).
        cat_cap = {
            c: min(DAILY_CATEGORY_CAPS.get(c, max_per_day), max_per_day)
            for c in cat_counts
        }

        days: List[List[Dict]] = [[] for _ in range(k)]
        cat_in_day = [defaultdict(int) for _ in range(k)]

        # Higher-scored POIs get first pick of their ideal day.
        for poi in sorted(geo, key=lambda p: p.get("persona_score", 0) or 0, reverse=True):
            cat = (poi.get("category") or "other").lower()
            day_order = sorted(
                range(k),
                key=lambda di: (poi["lat"] - centroids[di][0]) ** 2
                + (poi["lng"] - centroids[di][1]) ** 2,
            )

            placed = False
            # Pass 1: nearest day that respects both the day cap and category cap.
            for di in day_order:
                if len(days[di]) < max_per_day and cat_in_day[di][cat] < cat_cap[cat]:
                    days[di].append(poi)
                    cat_in_day[di][cat] += 1
                    placed = True
                    break
            # Pass 2: relax the category cap, keep the per-day cap.
            if not placed:
                for di in day_order:
                    if len(days[di]) < max_per_day:
                        days[di].append(poi)
                        cat_in_day[di][cat] += 1
                        placed = True
                        break
            # else: no room within max_per_day anywhere → drop (matches the
            # original truncation behaviour).

        # Order each day by nearest-neighbour visiting sequence, starting from
        # the stop nearest the hotel (so each day naturally departs your base).
        return [self._nearest_neighbour(d, anchor) for d in days if d]

    def distribute_evenly(
        self,
        pois: List[Dict],
        num_days: int,
        max_per_day: int = 5,
    ) -> List[List[Dict]]:
        """
        Fallback distribution: sort by persona_score and spread evenly
        across days without clustering.
        """
        sorted_pois = sorted(pois, key=lambda p: p.get("persona_score", 0), reverse=True)
        pois_per_day = max(1, min(max_per_day, max(1, len(sorted_pois) // max(num_days, 1))))

        days: List[List[Dict]] = []
        for d in range(num_days):
            chunk = sorted_pois[d * pois_per_day: (d + 1) * pois_per_day]
            if chunk:
                days.append(chunk)

        # Distribute leftovers
        leftover_start = num_days * pois_per_day
        for i, poi in enumerate(sorted_pois[leftover_start:]):
            if i < len(days):
                days[i].append(poi)

        return days

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _nearest_neighbour(self, pois: List[Dict], anchor: "tuple | None" = None) -> List[Dict]:
        """
        Sort POIs with a greedy nearest-neighbour heuristic.
        Starts from the stop nearest the ``anchor`` (hotel) when given,
        otherwise from the northernmost POI (natural 'morning start').
        """
        if len(pois) <= 1:
            return pois

        if anchor:
            a_lat, a_lng = anchor
            remaining = sorted(
                pois,
                key=lambda p: self._haversine(a_lat, a_lng, p.get("lat", 0), p.get("lng", 0)),
            )
        else:
            remaining = sorted(pois, key=lambda p: -p.get("lat", 0))
        ordered = [remaining.pop(0)]

        while remaining:
            cur     = ordered[-1]
            nearest = min(
                remaining,
                key=lambda p: self._haversine(
                    cur.get("lat", 0), cur.get("lng", 0),
                    p.get("lat", 0),   p.get("lng", 0),
                ),
            )
            ordered.append(nearest)
            remaining.remove(nearest)

        return ordered

    @staticmethod
    def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        R  = 6371.0
        φ1, φ2 = math.radians(lat1), math.radians(lat2)
        dφ, dλ = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
        a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
        return R * 2 * math.asin(math.sqrt(a))
