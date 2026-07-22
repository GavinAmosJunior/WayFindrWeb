from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Tuple
import heapq
from itertools import permutations

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
        # Grid Size: X from 1 to 65, Y from 0 to 48.
        # Y=0 is the Packing Station Aisle. Y=1 is Row A... Y=48 is Aisle above Row X.
        self.rows = "ABCDEFGHIJKLMNOPQRSTUVWX"
        self.row_map = {c: i for i, c in enumerate(self.rows)}
        self.indented_rows = {'B', 'D', 'F', 'H', 'J', 'L', 'N', 'P', 'R', 'T', 'V', 'X'}
        self.entrance_coord = (33, 0) # Center Aisle, Bottom
        
        # Build Logical Grid (0 = walkable aisle/gap, 1 = solid rack obstacle)
        self.costmap = [[0 for _ in range(49)] for _ in range(66)]
        self.build_obstacles()

    def build_obstacles(self):
        """Strictly enforces perimeter walls and rack obstacles."""
        for r_idx, r_letter in enumerate(self.rows):
            y = r_idx * 2 + 1 # Racks live on odd Y coordinates (1, 3, 5...)
            for c in range(1, 65):
                # Implement Serpentine Logic: Leave gaps at outer edges for indented rows
                if r_letter in self.indented_rows and (c == 1 or c == 64):
                    continue
                
                # X=33 is reserved for the Center Walkway. Skip it.
                x = c if c <= 32 else c + 1 
                self.costmap[x][y] = 1

    def get_access_points(self, locator_id: str) -> List[Tuple[int, int]]:
        """Finds the walkable aisle spaces immediately above or below a target rack."""
        parts = locator_id.split('-')
        row_letter = parts[1]
        col_num = int(parts[2])
        
        y = self.row_map[row_letter] * 2 + 1
        x = col_num if col_num <= 32 else col_num + 1
        
        access = []
        # Check aisle below
        if 0 <= y - 1 <= 48 and self.costmap[x][y - 1] == 0: access.append((x, y - 1))
        # Check aisle above
        if 0 <= y + 1 <= 48 and self.costmap[x][y + 1] == 0: access.append((x, y + 1))
        return access

    def a_star(self, start: Tuple[int, int], target: Tuple[int, int]):
        """Strict Orthogonal pathfinding ensuring paths never pass through obstacles."""
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
                
            # Strict Orthogonal movement only (No Diagonals)
            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nx, ny = current[0] + dx, current[1] + dy
                
                # Strict Grid Boundaries
                if 1 <= nx <= 65 and 0 <= ny <= 48:
                    if self.costmap[nx][ny] == 1:
                        continue # Cannot clip through rack
                        
                    tentative_g = g_score[current] + 1
                    if (nx, ny) not in g_score or tentative_g < g_score[(nx, ny)]:
                        came_from[(nx, ny)] = current
                        g_score[(nx, ny)] = tentative_g
                        f = tentative_g + abs(nx - target[0]) + abs(ny - target[1])
                        heapq.heappush(open_set, (f, (nx, ny)))
                        
        return [], float('inf')

    def optimize_sequence(self, locators: List[str]):
        if not locators: 
            return [], []

        nodes = locators
        best_overall_cost = float('inf')
        best_overall_sequence = []
        best_overall_legs = []

        for perm in permutations(nodes):
            current_states = [(self.entrance_coord, 0, [])]
            
            for loc in perm:
                next_states = []
                acc_points = self.get_access_points(loc)
                
                for target_acc in acc_points:
                    best_step_cost = float('inf')
                    best_step_leg = []
                    best_prev_state = None
                    
                    for prev_coord, prev_cost, prev_legs in current_states:
                        path, cost = self.a_star(prev_coord, target_acc)
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

            # Return back to Packing Station (33, 0)
            for prev_coord, prev_cost, prev_legs in current_states:
                path, cost = self.a_star(prev_coord, self.entrance_coord)
                total_cost = prev_cost + cost
                total_legs = prev_legs + [path]
                
                if total_cost < best_overall_cost:
                    best_overall_cost = total_cost
                    best_overall_sequence = perm
                    best_overall_legs = total_legs

        return list(best_overall_sequence), best_overall_legs

engine = WarehouseEngine()

class OptimizationRequest(BaseModel):
    locators: List[str]

@app.post("/api/optimize")
def optimize_route(req: OptimizationRequest):
    if not req.locators: raise HTTPException(status_code=400, detail="List cannot be empty")
    base_locators = list(set([ "-".join(loc.split('-')[:3]) for loc in req.locators ]))
    
    sequence, legs = engine.optimize_sequence(base_locators)
    
    formatted_legs = [[{"x": pt[0], "y": pt[1]} for pt in leg] for leg in legs]
    
    return {
        "status": "success",
        "optimized_sequence": sequence,
        "path_legs": formatted_legs
    }

@app.get("/")
def health_check(): return {"status": "online"}