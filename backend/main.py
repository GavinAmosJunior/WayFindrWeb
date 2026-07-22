from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Tuple, Optional
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
        # Map rows A-X to Y-coordinates (A=0, B=1, ... X=23)
        self.row_map = {chr(65 + i): i for i in range(24)}
        self.indented_rows = {'B', 'D', 'F', 'H', 'J', 'L', 'N', 'P', 'R', 'T', 'V', 'X'}
        # Entrance is logically located below Row A, in the center aisle
        self.entrance_coord = (32, -1) 

    def get_coordinates(self, locator_id: str) -> Tuple[int, int]:
        """Parses CTRA1-C-032-1 into logical (x, y) coordinates."""
        parts = locator_id.split('-')
        row_letter = parts[1]
        col_num = int(parts[2])
        return (col_num, self.row_map[row_letter])

    def calculate_walking_distance(self, coord1: Tuple[int, int], coord2: Tuple[int, int]) -> int:
        """Calculates distance enforcing the U-turn U-shape pathways."""
        x1, y1 = coord1
        x2, y2 = coord2
        
        # If in the same row, walk straight across
        if y1 == y2:
            return abs(x1 - x2)
            
        # If in different rows, force walking to the outer edges (x=0 or x=65)
        vertical_dist = abs(y1 - y2) * 2 
        dist_via_left = x1 + x2 + vertical_dist
        dist_via_right = (65 - x1) + (65 - x2) + vertical_dist
        
        return min(dist_via_left, dist_via_right)

    def optimize_sequence(self, locators: List[str]) -> List[str]:
        if not locators: return []

        # 1. Build Distance Matrix including the Entrance
        nodes = ['Entrance'] + locators
        coords = {'Entrance': self.entrance_coord}
        for loc in locators:
            coords[loc] = self.get_coordinates(loc)

        matrix = {n1: {n2: self.calculate_walking_distance(coords[n1], coords[n2]) for n2 in nodes} for n1 in nodes}

        # 2. Brute-force TSP permutation for the optimal loop
        best_sequence = None
        lowest_cost = float('inf')

        for perm in permutations(locators):
            current_cost = matrix['Entrance'][perm[0]]
            for i in range(len(perm) - 1):
                current_cost += matrix[perm[i]][perm[i+1]]
            current_cost += matrix[perm[-1]]['Entrance']
            
            if current_cost < lowest_cost:
                lowest_cost = current_cost
                best_sequence = perm
                
        return list(best_sequence)

engine = WarehouseEngine()

class OptimizationRequest(BaseModel):
    locators: List[str]

@app.post("/api/optimize")
def optimize_route(req: OptimizationRequest):
    if not req.locators:
        raise HTTPException(status_code=400, detail="Locator list cannot be empty")
    
    # Clean locators to base rack ID (e.g. CTRA1-C-032-2 -> CTRA1-C-032)
    base_locators = list(set([ "-".join(loc.split('-')[:3]) for loc in req.locators ]))
    optimized = engine.optimize_sequence(base_locators)
    
    return {
        "status": "success",
        "optimized_sequence": optimized
    }

@app.get("/")
def health_check():
    return {"status": "online"}