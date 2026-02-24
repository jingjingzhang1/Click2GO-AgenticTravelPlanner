"""
Route Optimizer
===============
Clusters verified POIs into geographic daily zones using K-Means,
then sorts each zone with a nearest-neighbour heuristic to minimise
backtracking during the day.
"""
import math
from typing import Dict, List


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
        import numpy as np
        from sklearn.cluster import KMeans

        # Safety: only cluster what has coordinates
        geo = [p for p in pois if p.get("lat") and p.get("lng")]
        if not geo:
            return self.distribute_evenly(pois, num_days, max_per_day)

        k = min(num_days, len(geo))
        coords = np.array([[p["lat"], p["lng"]] for p in geo])

        km = KMeans(n_clusters=k, random_state=42, n_init=10, max_iter=300)
        labels = km.fit_predict(coords)

        clusters: List[List[Dict]] = [[] for _ in range(k)]
        for poi, label in zip(geo, labels):
            clusters[label].append(poi)

        result = []
        for cluster in clusters:
            if cluster:
                sorted_c = self._nearest_neighbour(cluster)
                result.append(sorted_c[:max_per_day])

        return [d for d in result if d]

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

    def _nearest_neighbour(self, pois: List[Dict]) -> List[Dict]:
        """
        Sort POIs with a greedy nearest-neighbour heuristic.
        Starts from the northernmost POI (natural 'morning start').
        """
        if len(pois) <= 1:
            return pois

        remaining = sorted(pois, key=lambda p: -p.get("lat", 0))
        ordered   = [remaining.pop(0)]

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
