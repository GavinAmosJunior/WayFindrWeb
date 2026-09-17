from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Tuple
import heapq
from itertools import permutations
from datetime import datetime, timedelta, timezone
import json
import os
import sqlite3

app = FastAPI(title="PickPath AI Routing Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class WarehouseEngine:
    def __init__(self):
        #X from 1 to 65, Y from 0 to 48
        #Row A starting from 1-48, packing is at 0
        self.rows = "ABCDEFGHIJKLMNOPQRSTUVWX"
        self.row_map = {c: i for i, c in enumerate(self.rows)}
        self.indented_rows = {'B', 'D', 'F', 'H', 'J', 'L', 'N', 'P', 'R', 'T', 'V', 'X'}
        self.entrance_coord = (33, 0)
        
        self.costmap = [[0 for _ in range(49)] for _ in range(66)]
        self.build_obstacles()

    def build_obstacles(self):
        for r_idx, r_letter in enumerate(self.rows):
            y = r_idx * 2 + 1 #making shelves with gaps
            for c in range(1, 65):
                #empty an edge shelf for every indent
                if r_letter in self.indented_rows and (c == 1 or c == 64):
                    continue
                
                #make the hallway
                x = c if c <= 32 else c + 1 
                self.costmap[x][y] = 1

    def get_access_points(self, locator_id: str) -> List[Tuple[int, int]]:
        parts = locator_id.split('-')
        row_letter = parts[1]
        col_num = int(parts[2])
        
        y = self.row_map[row_letter] * 2 + 1
        x = col_num if col_num <= 32 else col_num + 1
        
        access = []
        #check aisle below
        if 0 <= y - 1 <= 48 and self.costmap[x][y - 1] == 0: access.append((x, y - 1))
        #check aisle above
        if 0 <= y + 1 <= 48 and self.costmap[x][y + 1] == 0: access.append((x, y + 1))
        return access

    def a_star(self, start: Tuple[int, int], target: Tuple[int, int]):
        open_set = []
        heapq.heappush(open_set, (0, start))
        came_from = {}
        g_score = {start: 0}
        
        while open_set:
            _, current = heapq.heappop(open_set)
            
            if current == target:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start)
                path.reverse()
                return path, g_score[target]
                
            #only x and y movements
            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nx, ny = current[0] + dx, current[1] + dy
                
                if 1 <= nx <= 65 and 0 <= ny <= 48:
                    if self.costmap[nx][ny] == 1:
                        continue
                        
                    tentative_g = g_score[current] + 1
                    if (nx, ny) not in g_score or tentative_g < g_score[(nx, ny)]:
                        came_from[(nx, ny)] = current
                        g_score[(nx, ny)] = tentative_g
                        f = tentative_g + abs(nx - target[0]) + abs(ny - target[1])
                        heapq.heappush(open_set, (f, (nx, ny)))
                        
        return [], float('inf')

    def optimize_sequence(self, locators: List[str]):
        if not locators: 
            return [], [], 0 #tak ganti

        best_overall_cost = float('inf')
        best_overall_sequence = []
        best_overall_legs = []
        path_cache = {}

        def route(start, target):
            key = (start, target)
            if key not in path_cache:
                path_cache[key] = self.a_star(start, target)
            return path_cache[key]

        for perm in permutations(locators):
            current_states = [(self.entrance_coord, 0, [])]
            
            for loc in perm:
                next_states = []
                acc_points = self.get_access_points(loc)
                
                for target_acc in acc_points:
                    best_step_cost = float('inf')
                    best_step_leg = []
                    best_prev_state = None
                    
                    for prev_coord, prev_cost, prev_legs in current_states:
                        path, cost = route(prev_coord, target_acc)
                        if cost < best_step_cost:
                            best_step_cost = cost
                            best_step_leg = path
                            best_prev_state = (prev_coord, prev_cost, prev_legs)
                    
                    prev_coord, prev_cost, prev_legs = best_prev_state
                    next_states.append((
                        target_acc, 
                        prev_cost + best_step_cost, 
                        prev_legs + [best_step_leg]
                    ))
                
                current_states = next_states

            #return back to packing station
            for prev_coord, prev_cost, prev_legs in current_states:
                path, cost = route(prev_coord, self.entrance_coord)
                total_cost = prev_cost + cost
                total_legs = prev_legs + [path]
                
                if total_cost < best_overall_cost:
                    best_overall_cost = total_cost
                    best_overall_sequence = perm
                    best_overall_legs = total_legs

        return list(best_overall_sequence), best_overall_legs, best_overall_cost

engine = WarehouseEngine()

ANALYTICS_DB_PATH = os.getenv(
    "ANALYTICS_DB_PATH",
    os.path.join(os.path.dirname(__file__), "route_analytics.db"),
)


def get_analytics_connection():
    connection = sqlite3.connect(ANALYTICS_DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_analytics_store():
    with get_analytics_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS route_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                route_json TEXT NOT NULL,
                total_steps INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS route_cells (
                run_id INTEGER NOT NULL,
                x INTEGER NOT NULL,
                y INTEGER NOT NULL,
                visit_order INTEGER NOT NULL,
                FOREIGN KEY (run_id) REFERENCES route_runs(id)
            );
            CREATE TABLE IF NOT EXISTS route_locators (
                run_id INTEGER NOT NULL,
                locator_id TEXT NOT NULL,
                stop_order INTEGER NOT NULL,
                FOREIGN KEY (run_id) REFERENCES route_runs(id)
            );
            CREATE INDEX IF NOT EXISTS idx_route_runs_recorded_at
                ON route_runs(recorded_at);
            CREATE INDEX IF NOT EXISTS idx_route_cells_run
                ON route_cells(run_id);
            CREATE INDEX IF NOT EXISTS idx_route_locators_run
                ON route_locators(run_id);
            """
        )


def record_route(sequence: List[str], legs: List[List[Tuple[int, int]]]):
    recorded_at = datetime.now(timezone.utc).isoformat()
    cells = [point for leg in legs for point in leg]
    with get_analytics_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO route_runs (recorded_at, route_json, total_steps) VALUES (?, ?, ?)",
            (recorded_at, json.dumps(sequence), len(cells)),
        )
        run_id = cursor.lastrowid
        connection.executemany(
            "INSERT INTO route_cells (run_id, x, y, visit_order) VALUES (?, ?, ?, ?)",
            [(run_id, point[0], point[1], order) for order, point in enumerate(cells)],
        )
        connection.executemany(
            "INSERT INTO route_locators (run_id, locator_id, stop_order) VALUES (?, ?, ?)",
            [(run_id, locator, order) for order, locator in enumerate(sequence)],
        )


def locator_coordinate(locator_id: str) -> Tuple[int, int]:
    parts = locator_id.split("-")
    row_index = engine.row_map[parts[1]]
    column = int(parts[2])
    x = column if column <= 32 else column + 1
    return x, row_index * 2 + 1


def make_recommendations(locator_counts):
    visited_locators = {row["locator_id"] for row in locator_counts}
    candidates = []
    for row_letter in engine.rows:
        for column in range(1, 65):
            if row_letter in engine.indented_rows and column in (1, 64):
                continue
            locator = f"CTRA1-{row_letter}-{column:03d}"
            if locator in visited_locators:
                continue
            x, rack_y = locator_coordinate(locator)
            access_y = rack_y - 1 if rack_y > 0 else rack_y + 1
            candidates.append((abs(x - engine.entrance_coord[0]) + access_y, locator))

    candidates.sort()
    recommendations = []
    reserved_locators = set()
    for row in locator_counts[:10]:
        current_x, current_y = locator_coordinate(row["locator_id"])
        current_distance = abs(current_x - engine.entrance_coord[0]) + max(current_y - 1, 0)
        source_prefix = row["locator_id"].split("-")[0]
        closer = next(
            (
                candidate
                for _, _, candidate in sorted(
                    (
                        (
                            abs(locator_coordinate(candidate)[0] - current_x)
                            + abs(locator_coordinate(candidate)[1] - current_y),
                            distance,
                            candidate,
                        )
                        for distance, candidate in candidates
                        if candidate not in reserved_locators
                        and candidate.startswith(f"{source_prefix}-")
                        and distance < current_distance * 0.75
                    )
                )
            ),
            None,
        )
        if closer:
            reserved_locators.add(closer)
            recommendations.append(
                {
                    "from_locator": row["locator_id"],
                    "suggested_locator": closer,
                    "visits": row["visits"],
                    "reason": "Frequently visited and the candidate is closer to the packing station.",
                    "requires_inventory_check": True,
                }
            )
    return recommendations[:5]


initialize_analytics_store()

class OptimizationRequest(BaseModel):
    locators: List[str]

@app.post("/api/optimize")
def optimize_route(req: OptimizationRequest):
    if not req.locators: raise HTTPException(status_code=400, detail="List cannot be empty")
    base_locators = {"-".join(loc.split('-')[:3]) for loc in req.locators}
    sequence, legs, total_grid_steps = engine.optimize_sequence(base_locators)
    record_route(sequence, legs)
    grid_step_meters = 0.725
    walking_speed_mps = 1.4 
    pick_time_seconds = 90 
    distance_meters = total_grid_steps * grid_step_meters
    estimated_time_seconds = (distance_meters / walking_speed_mps) + (len(sequence) * pick_time_seconds)
    
    formatted_legs = [[{"x": pt[0], "y": pt[1]} for pt in leg] for leg in legs]
    
    return {
        "status": "success",
        "optimized_sequence": sequence,
        "path_legs": formatted_legs,
        "distance_meters": distance_meters,
        "estimated_time_seconds": round(estimated_time_seconds)
    }


@app.get("/api/analytics")
def route_analytics(days: int = 30):
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="days must be between 1 and 365")

    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with get_analytics_connection() as connection:
        route_summary = connection.execute(
            """
            SELECT COUNT(*) AS total_routes, COALESCE(SUM(total_steps), 0) AS total_steps,
                   COALESCE(AVG(total_steps), 0) AS average_route_steps
            FROM route_runs WHERE recorded_at >= ?
            """,
            (since,),
        ).fetchone()
        cell_counts = connection.execute(
            """
            SELECT x, y, COUNT(*) AS visits FROM route_cells
            WHERE run_id IN (SELECT id FROM route_runs WHERE recorded_at >= ?)
            GROUP BY x, y ORDER BY visits DESC
            """,
            (since,),
        ).fetchall()
        locator_counts = connection.execute(
            """
            SELECT locator_id, COUNT(*) AS visits FROM route_locators
            WHERE locator_id != 'packingStation'
              AND run_id IN (SELECT id FROM route_runs WHERE recorded_at >= ?)
            GROUP BY locator_id ORDER BY visits DESC
            """,
            (since,),
        ).fetchall()
        latest_route = connection.execute(
            """
            SELECT route_json FROM route_runs
            WHERE recorded_at >= ?
            ORDER BY recorded_at DESC LIMIT 1
            """,
            (since,),
        ).fetchone()
        latest_cells = connection.execute(
            """
            SELECT x, y FROM route_cells
            WHERE run_id = (
                SELECT id FROM route_runs
                WHERE recorded_at >= ?
                ORDER BY recorded_at DESC LIMIT 1
            )
            ORDER BY visit_order
            """,
            (since,),
        ).fetchall()

    return {
        "days": days,
        "from": since,
        "summary": dict(route_summary),
        "heatmap": [dict(row) for row in cell_counts],
        "latest_route": {
            "sequence": json.loads(latest_route["route_json"]) if latest_route else [],
            "path": [dict(row) for row in latest_cells],
        },
        "hotspot_locators": [dict(row) for row in locator_counts[:10]],
        "recommendations": make_recommendations(locator_counts),
    }

@app.get("/")
def health_check(): return {"status": "online"}