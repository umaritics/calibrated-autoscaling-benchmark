from locust import HttpUser, task, between, LoadTestShape
import pandas as pd
import math

# Load the generated traces
df = pd.read_csv('data/workload_traces.csv')
# Choose which regime to test here
REGIME = 'spike' 
# Multiply the trace demand by a factor if needed to create RPS
demand_profile = df[REGIME].values

class MyUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def get_root(self):
        self.client.get("/")

class TraceShape(LoadTestShape):
    """
    A shape class that scales user count based on the trace values.
    """
    step_duration = 5 # Each trace step runs for 5 seconds
    
    def tick(self):
        run_time = self.get_run_time()
        step = int(run_time / self.step_duration)
        
        if step >= len(demand_profile):
            return None # Stop test
            
        target_users = int(math.ceil(demand_profile[step]))
        # spawn rate = how many users to add/remove per second to reach target
        spawn_rate = 10 
        
        return (target_users, spawn_rate)
