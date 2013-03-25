import pulp as lp
import numpy as np
import time

class LPSolver:
    """ Linear Program Solver for the small models
    """
    
    def __init__(self, ISO):
        self.ISO = ISO
        
        
    def full_setup_and_solve(self, reserve=True, proportion=True,
                             combined=True, transmission=True):
                             
        begin = time.time()
        self.setup_lp(reserve=reserve, proportion=proportion,
                      combined=combined, transmission=transmission)
        self.setup_time = time.time() - begin
        
        self.solve_lp()
        self.return_dispatch()
    
    def setup_lp(self, reserve=True, proportion=True, combined=True,
                 transmission=True):
        """ Set up the Linear Program by creating an objective function and 
            passing the requisite variables to it.
        
        """
        
        # Get the Constraints and lists for model creation simplification
        eb = self.ISO.energy_bands
        rb = self.ISO.reserve_bands
        tb = self.ISO.transmission_bands
        nd  = self.ISO.all_nodes
        
        et = self.ISO.energy_totals
        rt = self.ISO.reserve_totals
        tt = self.ISO.transmission_totals
        
        ebmap = self.ISO.energy_band_map
        rbmap = self.ISO.reserve_band_map
        tbmap = self.ISO.transmission_band_map
               
        ebp = self.ISO.energy_band_prices
        rbp = self.ISO.reserve_band_prices

        ebm = self.ISO.energy_band_maximum
        rbm = self.ISO.reserve_band_maximum
        tbm = self.ISO.transmission_band_maximum
        
        etm = self.ISO.energy_total_maximum
        ttm = self.ISO.transmission_total_maximum
        rbpr = self.ISO.reserve_band_proportion
        
        spin = self.ISO.spinning_station_names
        spin_map = self.ISO.spin_map
        
        node_map = self.ISO.node_energy_map
        demand = self.ISO.node_demand
        
        node_t_map = self.ISO.node_t_map
        td = self.ISO.node_transmission_direction
        
        rzones = self.ISO.reserve_zone_names
        rzone_g = self.ISO.reserve_zone_generators
        rzone_t = self.ISO.reserve_zone_transmission
        
        rz_providers = self.ISO.reserve_zone_reserve
        
        # Set up the linear program        
        
        self.lp = lp.LpProblem("Model Dispatch", lp.LpMinimize)
        
        # Add variables
        ebo = lp.LpVariable.dicts("Energy_Band", eb, 0)
        rbo = lp.LpVariable.dicts("Reserve_Band", rb, 0)
        tbo = lp.LpVariable.dicts("Transmission_Band", tb)
        
        eto = lp.LpVariable.dicts("Energy_Total", et, 0)
        rto = lp.LpVariable.dicts("Reserve_Total", rt, 0)
        tto = lp.LpVariable.dicts("Transmission_Total", tt)
        
        node_inj = lp.LpVariable.dicts("Nodal_Inject", nd)
        
        risk = lp.LpVariable.dicts("Risk", rzones)
        
        
        # Map the add Constraint method to a simpler string
        addC = self.lp.addConstraint
        SUM = lp.lpSum
        
        

        # Objective function
        self.lp.setObjective(SUM([ebo[i] * ebp[i] for i in eb]) +\
                             SUM([rbo[j] * rbp[j] for j in rb]))
                             
        # Begin Adding Constraint
        
        # Nodal Dispatch
        for n in nd:
            n1 = '_'.join([n, 'Energy_Price'])
            n2 = '_'.join([n, 'Nodal_Transmission'])
            addC(node_inj[n] == SUM([eto[i] for i in node_map[n]]) - demand[n], n1)
            addC(node_inj[n] == SUM([tto[i] * td[n][i] for i in node_t_map[n]]), n2)
        
        # Individual Band Offer
        for i in eb:
            name = '_'.join([i, 'Band_Energy'])
            addC(ebo[i] <= ebm[i], name)
            
        # Reserve Band Offer
        for j in rb:
            name = '_'.join([j, 'Band_Reserve'])
            addC(rbo[j] <= rbm[j], name)
            
        # Transmission band Offer
        for t in tb:
            addC(tbo[t] <= tbm[t])
            addC(tbo[t] >= tbm[t] * -1)
            
        # Energy Total Offer
        for i in et:
            name = '_'.join([i, 'Total_Energy'])
            addC(SUM([ebo[j] for j in ebmap[i]]) == eto[i], name)
            
        # Reserve Total Offer
        for i in rt:
            name = '_'.join([i, 'Total_Reserve'])
            addC(SUM([rbo[j] for j in rbmap[i]]) == rto[i], name)
            
        # Transmission Total offer
        for i in tt:
            addC(SUM([tbo[j] for j in tbmap[i]]) == tto[i])
            addC(tto[i] <= ttm[i])
            addC(tto[i] >= ttm[i] * -1)
            
        # Spinning Reserve Constraints
        for i in spin:
            name = '_'.join([i, 'Combined_Dispatch'])
            addC(rto[i] + eto[i] <= etm[i], name)
            
            for j in spin_map[i]:
                name = '_'.join([j, 'Prop'])
                addC(rbo[j] <= rbpr[j] * eto[i], name)
                
        
        # Risk Constraints
        
        for r in rzones:
            # Generation Risk
            for i in rzone_g[r]:
                name = '_'.join([r, i])
                addC(risk[r] >= eto[i], name)
        
            # Transmission Risk        
            for t in rzone_t[r]:
                name = '_'.join([r, t])
                addC(risk[r] >= -1 * tto[t], name)
                
        # Reserve Dispatch
        for r in rzones:
            n1 = '_'.join([r, 'Reserve_Price'])
            addC(SUM(rto[i] for i in rz_providers[r]) - risk[r] >= 0., n1)
        
        
    def write_lp(self, name="Test.lp"):
        self.lp.writeLP(name)
        
    def solve_lp(self):
        begin = time.time()
        self.lp.solve(lp.COIN_CMD())
        solved = time.time() - begin
        self.solution_time = solved
        if self.lp.status is not 1:
            print "LP Status is:", lp.LpStatus[self.lp.status]
            print "Dumping LP"
            self.write_lp(name="Infeasiable_LP_Debug.lp")
            print 'Objective function value is:', lp.value(self.lp.objective)
        
        
    def get_values(self):
        for val in self.lp.variables():
            print val, val.varValue
            
            
    def get_shadow_values(self):
        for n in self.lp.constraints:
            try:
                print n, self.lp.constraints[n].pi
            except:
                print n, 0
        
    def get_prices(self):
        for n in self.lp.constraints:
            if "Price" in n:
                try:
                    print n, self.lp.constraints[n].pi
                except:
                    print n, "no value"
                    
                    
    def return_dispatch(self):
        """ Return the entire dispatch from the solved linear program """
        begin = time.time()
        self._energy_prices()
        self._reserve_prices()
        self._energy_dispatch()
        self._reserve_dispatch()
        self._branch_flow()
        self._log_duals()
        self.dispatch_time = time.time() - begin
        
    def print_time(self):
        print "Model created in %0.3f ms" % float(self.setup_time * 1000)
        print "Model solved in %0.3f ms" % float(self.solution_time * 1000)
        print "Model post process in %0.3f ms" % float(self.dispatch_time * 1000)
        
                    

    def _energy_prices(self):
        """ Will return the energy prices to the respective nodes """
        # Get the energy prices
        prices = {n.split('_')[0]: -1* self.lp.constraints[n].pi 
                    for n in self.lp.constraints if 'Energy_Price' in n}
                               
        # Add tonode  
        for node in prices:
            self.ISO.node_name_map[node].add_price(prices[node])
            
            
    def _reserve_prices(self):
        """ Will return the reserve prices to the respective reserve zones """
        prices = {n.split('_')[0]: self.lp.constraints[n].pi
                    for n in self.lp.constraints if 'Reserve_Price' in n}
                
        # Add to Reserve Zone
        for rzone in prices:
            self.ISO.reserve_zone_name_map[rzone].add_price(prices[rzone])
            

    def _energy_dispatch(self):
        """ Returns the energy dispatch to the respective stations """
        dispatch = {v.name.split('_')[-1] : v.varValue
                    for v in self.lp.variables() if 'Energy_Total' in v.name}
                        
        for station in dispatch:
            self.ISO.station_name_map[station].add_dispatch(dispatch[station])
            
            
    def _reserve_dispatch(self):
        """ Return the reserve dispatch to the respective units """
        dispatch = {v.name.split('_')[-1] : v.varValue
                    for v in self.lp.variables() if 'Reserve_Total' in v.name}
                    
        for unit in dispatch:
            self.ISO.reserve_name_map[unit].add_res_dispatch(dispatch[unit])
            

    def _branch_flow(self):
        """ Return the transfer on branches """
        dispatch = {'_'.join(v.name.split('_')[-2:]): v.varValue
                    for v in self.lp.variables()
                    if 'Transmission_Total' in v.name}
                    
        for b in dispatch:
            self.ISO.branch_name_map[b].add_flow(dispatch[b])
            
    def _log_duals(self):
        """ Log the dual variables for later analysis"""
        duals = {}
        for n in self.lp.constraints:
            if 'Price' not in n:
                try:
                    duals[n] = self.lp.constraints[n].pi
                except:
                    duals[n] = 0.
        
        self.duals = duals
        self.non_zero_duals = {n: duals[n] for n in duals if duals[n] != 0.}
        self.negative_duals = {n: duals[n] for n in duals if duals[n] < 0.}
        
                
if __name__ == '__main__':
    pass
