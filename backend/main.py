from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Tuple, Optional
import numpy as np
import string
import heapq
from itertools import permutations

app = FastAPI(title="PickPath AI Routing Engine")

# Enable CORS so your frontend can call this backend from local or any domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class WarehouseNavigator:
    def __init__(self, resolution=0.5):
        self.resolution = resolution
        self.rows = list(string.ascii_uppercase)[:24]
        self.total_columns = 64
        self.shelf_width = 1.0
        self.shelf_height = 0.8
        self.col_spacing = 1.2
        self.row_spacing = 3.0
        self.center_aisle = 6.0
        
        self.max_x = (self.total_columns * self.col_spacing) + self.center_aisle + 5.0
        self.max_y = (len(self.rows) * self.row_spacing) + 2.0
        self.grid_width = int(self.max_x / self.resolution)
        self.grid_height = int(self.max_y / self.resolution)
        
        self.costmap = np.zeros((self.grid_width, self.grid_height))
        self.shelf_coordinates = {}
        self.build_costmap()

    def build_costmap(self):
        for r_idx, row_letter in enumerate(self.rows):
            is_alternating_gap_row = (r_idx % 2 != 0)
            for c_idx in range(1, self.total_columns + 1):
                x_pos = c_idx * self.col_spacing
                if c_idx > 32: x_pos += self.center_aisle
                y_pos = r_idx * self.row_spacing
                
                if row_letter == 'A' and c_idx in [30, 31, 32]: continue
                if row_letter == 'B' and c_idx in [31, 32]: continue
                if is_alternating_gap_row and c_idx in [1, 2, 63, 64]: continue
                
                locator_id = f"CTRA1-{row_letter}-{c_idx:03d}-1"
                self.shelf_coordinates[locator_id] = (x_pos, y_pos)
                self._mark_obstacle(x_pos, y_pos, self.shelf_width, self.shelf_height)

        center_aisle_start = 32 * self.col_spacing
        center_aisle_end = center_aisle_start + self.center_aisle
        
        self._mark_obstacle(0, -3.0, center_aisle_start, 2.9) 
        self._mark_obstacle(center_aisle_end, -3.0, self.max_x - center_aisle_end, 2.9)

        comp_width = (3 * self.col_spacing) - (self.col_spacing - self.shelf_width)
        self._mark_obstacle(30 * self.col_spacing, 0, comp_width, self.shelf_height)
        stair_width = (2 * self.col_spacing) - (self.col_spacing - self.shelf_width)
        self._mark_obstacle(31 * self.col_spacing, 1 * self.row_spacing, stair_width, self.shelf_height)

    def _mark_obstacle(self, x, y, width, height):
        start_gx, start_gy = self._world_to_grid(x, y)
        end_gx, end_gy = self._world_to_grid(x + width, y + height)
        buffer = 1
        start_gx, start_gy = max(0, start_gx - buffer), max(0, start_gy - buffer)
        end_gx, end_gy = min(self.grid_width, end_gx + buffer), min(self.grid_height, end_gy + buffer)
        for gx in range(start_gx, end_gx):
            for gy in range(start_gy, end_gy):
                self.costmap[gx][gy] = 1

    def _world_to_grid(self, x, y):
        adjusted_y = y + 3.0 
        return int(x / self.resolution), int(adjusted_y / self.resolution)

    def _grid_to_world(self, gx, gy):
        return (gx * self.resolution), (gy * self.resolution) - 3.0

    def a_star(self, start_coord, goal_coord):
        start_node = self._world_to_grid(*start_coord)
        goal_node = self._world_to_grid(*goal_coord)

        open_set = []
        heapq.heappush(open_set, (0, start_node))
        came_from = {}
        g_score = {start_node: 0}
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]

        while open_set:
            _, current = heapq.heappop(open_set)

            if current == goal_node:
                path = []
                while current in came_from:
                    path.append(self._grid_to_world(*current))
                    current = came_from[current]
                path.reverse()
                return path, g_score[goal_node]

            for dx, dy in directions:
                neighbor = (current[0] + dx, current[1] + dy)
                if 0 <= neighbor[0] < self.grid_width and 0 <= neighbor[1] < self.grid_height:
                    if self.costmap[neighbor[0]][neighbor[1]] == 1:
                        continue 

                    tentative_g = g_score[current] + 1
                    if neighbor not in g_score or tentative_g < g_score[neighbor]:
                        came_from[neighbor] = current
                        g_score[neighbor] = tentative_g
                        h = abs(neighbor[0] - goal_node[0]) + abs(neighbor[1] - goal_node[1])
                        f_score = tentative_g + h
                        heapq.heappush(open_set, (f_score, neighbor))
                        
        return [], float('inf')

    def optimize_route(self, entrance, pick_list):
        # Normalize incoming locator IDs (ensure shelf suffix matches grid)
        normalized_picks = []
        for p in pick_list:
            parts = p.split('-')
            if len(parts) >= 3:
                norm = f"{parts[0]}-{parts[1]}-{parts[2]}-1"
                if norm in self.shelf_coordinates and norm not in normalized_picks:
                    normalized_picks.append(norm)

        if not normalized_picks:
            return [], [], 0

        nodes = ['Entrance'] + normalized_picks
        coords = {'Entrance': entrance}
        for p in normalized_picks:
            target = list(self.shelf_coordinates[p])
            target[1] += 1.5 
            coords[p] = target
            
        cost_matrix = {}
        path_matrix = {}
        for i in nodes:
            cost_matrix[i] = {}
            path_matrix[i] = {}
            for j in nodes:
                if i == j:
                    cost_matrix[i][j] = 0
                    path_matrix[i][j] = []
                else:
                    path, cost = self.a_star(coords[i], coords[j])
                    cost_matrix[i][j] = cost
                    path_matrix[i][j] = path
                    
        best_sequence = None
        lowest_total_cost = float('inf')
        
        for perm in permutations(normalized_picks):
            current_cost = cost_matrix['Entrance'][perm[0]]
            for i in range(len(perm) - 1):
                current_cost += cost_matrix[perm[i]][perm[i+1]]
            current_cost += cost_matrix[perm[-1]]['Entrance']
            
            if current_cost < lowest_total_cost:
                lowest_total_cost = current_cost
                best_sequence = perm
                
        full_path_coords = []
        current_node = 'Entrance'
        for next_node in best_sequence:
            full_path_coords.extend(path_matrix[current_node][next_node])
            current_node = next_node
        full_path_coords.extend(path_matrix[current_node]['Entrance'])
        
        return list(best_sequence), full_path_coords, lowest_total_cost

# Global Navigator Instance
navigator = WarehouseNavigator(resolution=0.5)

class OptimizationRequest(BaseModel):
    locators: List[str]
    entrance: Optional[Tuple[float, float]] = (41.5, -1.0)

@app.post("/api/optimize")
def optimize_route(req: OptimizationRequest):
    if not req.locators:
        raise HTTPException(status_code=400, detail="Locator list cannot be empty")
    
    sequence, path_coords, cost = navigator.optimize_route(req.entrance, req.locators)
    return {
        "status": "success",
        "optimized_sequence": sequence,
        "path_coordinates": path_coords,
        "total_cost_units": cost
    }

@app.get("/")
def health_check():
    return {"status": "online", "message": "PickPath AI Python Engine is Active"}