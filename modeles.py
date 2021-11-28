# Imports 
import pyomo.environ as pyo
from pyomo.opt import SolverFactory
import pandas as pd
import numpy as np
import csv



class modele : 
    
        
    
    def __init__(self, Q_tec, Volume_str, S) : 
        
        self.Q_tec = Q_tec
        self.Volume_str = Volume_str
        self.S = S
        
        
        
        # Months 
        self.m = ["jan","feb", "mar","apr","jun","jul","aug","sep","oct","nov","dec"]
        # Technologies 
        self.tec = list(self.Q_tec.index)
        # Storage technologies
        self.stor = ["phs","battery","methanation"]
        # Power plants
        self.gen = list(set(list(self.Q_tec.index)) - set(self.stor))
        # Variable tec
        self.vre = ["offshore","onshore","pv"]
        
        
        # Non combustible generation tec
        #self.ncomb = ["offshore","onshore","pv","phs","battery"]
        # Combustible generation tec
        #self.comb = ["biogas","methanation"]
        
        # Technologies for upward FRR 
        self.frr = ["phs","battery"] + ["lake"]*("lake" in self.gen)
        
        print("Technologies utilisées :", self.tec)
        
        # Initialisation du modèle Pyomo 
        self.model = pyo.ConcreteModel()
        
        
        
    def load_param(self, path) : 
        
        print("Chargement des paramètres ...")
        
        # profil des VRE par heure (éolien + PV)
        self.load_factor = pd.read_csv(path + "vre_profiles2006.csv", index_col=[0, 1], squeeze=True, header=None)
        # Additional FRR requirement for variable renewable energies because of forecast errors
        self.epsilon = pd.read_csv(path+"reserve_requirements.csv", index_col=0, squeeze=True, header=None)
        # Demand profile in each our in GW
        self.demand_2050 = pd.read_csv(path + "demand2050_ademe.csv",index_col=0, squeeze=True, header=None)
        # Variable operation and maintenance costs in M€/GWh
        self.vOM = pd.read_csv(path + "vO&M.csv", index_col=0, squeeze=True, header=None)
        # Monthly lake inflows in GWh
        self.lake_inflows = pd.read_csv(path + "lake_inflows.csv", index_col=0, squeeze=True, header=None)
        # profil des rivières par heure
        self.gene_river = pd.read_csv(path + "run_of_river.csv", header = None , index_col = 0, squeeze = True)
        
        # Annualized power capex cost in M€/GW/year
        self.capex = pd.read_csv(path + "annuities.csv", index_col=0, squeeze=True, header=None)
        # Existing capacities of the technologies by December 2017 in GW
        self.capa_ex = pd.read_csv(path+"existing_capas.csv", index_col=0, squeeze=True, header=None)
        # Annualized energy capex cost of storage technologies in M€/GWh/year
        self.capex_en = pd.read_csv(path + "str_annuities.csv", index_col=0, squeeze=True, header=None)
        # Annualized fixed operation and maintenance costs M€/GW/year
        self.fOM = pd.read_csv(path+"fO&M.csv", index_col=0, squeeze=True, header=None)
        s_capex = [0,0,84.16086]
        self.s_capex = pd.Series(s_capex, index = self.stor)
        # charging related fOM of storage in M€/GW/year
        s_opex = [7.5,0,59.25]
        self.s_opex = pd.Series(s_opex, index = self.stor)



        # maxium energy can be generated by biogas in TWh
        self.max_biogas = 15
        # uncertainty coefficient for hourly demand
        self.load_uncertainty = 0.01
        # load variation factor
        self.delta = 0.1
        # charging efifciency of storage technologies
        eta_in = [0.95,0.9,0.59]
        self.eta_in = pd.Series(eta_in, index = self.stor)
        # discharging efficiency of storage technolgoies
        eta_out = [0.9, 0.95, 0.45]
        self.eta_out = pd.Series(eta_out, index = self.stor)


        self.epsilon = self.epsilon.rename(index ={"PV": "pv"})
        self.vOM = self.vOM.rename(index={"Onshore": "onshore", "PV":"pv", "PHS":"phs", "Battery":"battery"})
        self.fOM = self.fOM.rename(index={"Offshore": "offshore", "Onshore": "onshore", "PV":"pv", "PHS":"phs", "Battery":"battery"})
        self.capex = self.capex.rename(index={"Offshore": "offshore", "Onshore": "onshore", "PV":"pv", "PHS":"phs", "Battery":"battery"})
        
        

        
    def init_set(self):
        
        print("Initialisation des sets...")
        self.first_hour = 0
        self.last_hour = len(self.demand_2050)
        days_in_feb = 672

        hours_by_months = {1: 744, 2: days_in_feb, 3: 744, 4: 720, 5: 744, 6: 720, 7: 744, 8: 744, 9: 720, 10: 744, 11: 720, 12: 744}
        self.months_hours = {1: range(0, 744), 2: range(744, 1440), 3: range(1440, 2184), 4: range(2184, 2904),
                        5: range(2904, 3648), 6: range(3648, 4368), 7: range(4368, 5112),
                        8: range(5112, 5856), 9: range(5856, 6576), 10: range(6576, 7320), 11: range(7320, 8040),
                        12: range(8039, self.last_hour)}
        
        self.months_hours = dict(zip(self.m,list(self.months_hours.values()))) 

        #Range of hour in one year
        self.model.h = pyo.RangeSet(self.first_hour,self.last_hour-1)
        #Months
        self.model.months = pyo.Set(initialize = self.m)
        #Technologies
        self.model.tec = pyo.Set(initialize=self.tec)
        #Power plants
        self.model.gen = pyo.Set(initialize=self.gen)
        #Variables Technologies
        self.model.vre = pyo.Set(initialize=self.vre)
        #Storage Technologies
        self.model.str = pyo.Set(initialize=self.stor)
        #Technologies for upward FRR
        self.model.frr =pyo.Set(initialize=self.frr)
        
        
    def init_variable(self):
        # Définitions des variables à optimiser
        print("Définition des variables à optimiser ...")
        # Hourly energy generation in GWh/h
        self.model.gene = pyo.Var(((tec, h) for tec in self.model.tec for h in self.model.h), within=pyo.NonNegativeReals,initialize=0)

        # Hourly electricity input of battery storage GW
        self.model.storage = pyo.Var(((storage, h) for storage in self.model.str for h in self.model.h), within=pyo.NonNegativeReals,initialize=0)

        # Energy stored in each storage technology in GWh = Stage of charge
        self.model.stored = pyo.Var(((storage, h) for storage in self.model.str for h in self.model.h), within=pyo.NonNegativeReals,initialize=10)

        # Required upward frequency restoration reserve in GW    
        self.model.reserve = pyo.Var(((reserve, h) for reserve in self.model.frr for h in self.model.h), within=pyo.NonNegativeReals,initialize=0)
        
        
    # définition des contraintes : 
    
    
    def generation_vre_constraint_rule(self, model, h, vre):
        """Get constraint on variables renewable profiles generation."""
        return model.gene[vre, h] == self.Q_tec[vre] * self.load_factor[vre,h]

    def generation_river_rule(self, model, h):
        return model.gene["river", h] == self.Q_tec["river"]*self.gene_river[h]
    
    def generation_capacity_constraint_rule(self, model, h, tec):
        """Get constraint on maximum power for non-VRE technologies."""
        return self.Q_tec[tec] >= model.gene[tec,h]

    def biogas_constraint_rule(self, model):
        """Get constraint on biogas."""
        gene_biogas = sum(model.gene['biogas', hour] for hour in model.h)
        return gene_biogas <= self.max_biogas * 1000

    def frr_capacity_constraint_rule(self, model, h, frr):
        """Get constraint on maximum generation including reserves"""
        return self.Q_tec[frr] >= model.gene[frr, h] + model.reserve[frr, h]

    def reserves_constraint_rule(self, model, h):
        """Get constraint on water for lake reservoirs."""
        res_req = sum(self.epsilon[vre] * self.Q_tec[vre] for vre in model.vre)
        load_req = self.demand_2050[h] *self.load_uncertainty * (1 + self.delta)
        return sum(model.reserve[frr, h] for frr in model.frr) ==  res_req + load_req
    
    def storing_constraint_rule(self, model, h, storage_tecs):
        """Get constraint on storing."""
        hPOne = h+1 if h<(self.last_hour-1) else 0
        charge = model.storage[storage_tecs, h] * self.eta_in[storage_tecs]
        discharge =  model.gene[storage_tecs, h] / self.eta_out[storage_tecs]
        flux = charge - discharge
        return model.stored[storage_tecs, hPOne] == model.stored[storage_tecs, h] + flux

    def storage_constraint_rule(self, model,storage_tecs):
        """Get constraint on stored energy to be equal at the end than at the start."""
        first = model.stored[storage_tecs, self.first_hour]
        last = model.stored[storage_tecs, self.last_hour-1]
        charge = model.storage[storage_tecs, self.last_hour-1] * self.eta_in[storage_tecs]
        discharge = model.gene[storage_tecs, self.last_hour-1] / self.eta_out[storage_tecs]
        flux = charge - discharge
        return first == last + flux
    
    def stored_capacity_constraint(self, model, h, storage_tecs):
        """Get constraint on maximum energy that is stored in storage units"""
        return model.stored[storage_tecs,h] <= self.Volume_str[storage_tecs]

    def stored_capacity_constraint2(self, model, h, storage_tecs):
        """Get constraint on maximum energy that is stored in storage units"""
        return model.storage[storage_tecs, h] <= self.S[storage_tecs]
    
    def lake_reserve_constraint_rule(self, model, month):
        """Get constraint on maximum monthly lake generation."""
        return sum(model.gene['lake', hour] for hour in self.months_hours[month]) <= self.lake_inflows[month] * 1000

    

    
    def adequacy_constraint_rule(self, model, h):
        """Get constraint for 'supply/demand relation'"""
        sto = sum(model.storage[stor, h] for stor in model.str)
        return sum(model.gene[tec, h] for tec in model.tec) >= (self.demand_2050[h] + sto )

    def objective_rule(self, model):
        """Get constraint for the final objective function."""
        return (sum(sum(model.gene[tec, h] * self.vOM[tec] for h in model.h) for tec in model.tec))/1000
    
    def add_constraints(self):
        
        print("Ajout des contraintes ...")
        # contraintes sur la génération
        self.model.generation_vre_constraint = pyo.Constraint(self.model.h, self.model.vre, rule=self.generation_vre_constraint_rule)
        self.model.generation_capacity_constraint = pyo.Constraint(self.model.h, self.model.tec, rule=self.generation_capacity_constraint_rule)
        self.model.generation_biogas = pyo.Constraint(rule=self.biogas_constraint_rule)
        
        if ("river" in self.tec) : 
            self.model.generation_river = pyo.Constraint(self.model.h, rule=self.generation_river_rule)
            
        if ("lake" in self.tec) : 
            self.model.lake_constraint = pyo.Constraint(self.model.months, rule = self.lake_reserve_constraint_rule)

        # contraintes sur les frr
        self.model.frr_constraint =  pyo.Constraint(self.model.h, self.model.frr, rule=self.frr_capacity_constraint_rule)
        self.model.reserves_constraint = pyo.Constraint(self.model.h, rule=self.reserves_constraint_rule)

        # contraintes sur STORED
        self.model.storing_constraint = pyo.Constraint(self.model.h,self.model.str, rule=self.storing_constraint_rule)
        self.model.storage_constraint = pyo.Constraint(self.model.str, rule=self.storage_constraint_rule)

        self.model.stored_capacity_constraint = pyo.Constraint(self.model.h, self.model.str, rule=self.stored_capacity_constraint)
        self.model.stored_capacity_constraint2 = pyo.Constraint(self.model.h, self.model.str, rule=self.stored_capacity_constraint2)
        

        self.model.adequacy_constraint =  pyo.Constraint(self.model.h, rule=self.adequacy_constraint_rule)
        
        #Creation of the objective 
        self.model.objective = pyo.Objective(rule=self.objective_rule)

        
    def optimisation(self):
        print("Optimisation ...")
        opt = SolverFactory('cbc')
        self.results = opt.solve(self.model)
        
    
    def cost(self):
        """Return total cost (billion euros) and cost per MWh produced (euros/MWh) """
        
        
        const = sum((self.Q_tec[tec] - self.capa_ex[tec]) * self.capex[tec] for tec in self.model.tec) \
           + sum((self.Volume_str[storage_tecs]) * self.capex_en[storage_tecs] for storage_tecs in self.model.str)\
           + sum(self.Q_tec[tec] * self.fOM[tec] for tec in self.model.tec)\
           + sum(self.S[storage_tecs] * (self.s_opex[storage_tecs] + self.s_capex[storage_tecs]) for storage_tecs in self.model.str)
        
        
        sumgene = sum(pyo.value(self.model.gene[gen,hour]) for hour in self.model.h for gen in self.model.gen) / 1000
        c_tot = pyo.value(self.model.objective) +const
        c_mwh_produced = c_tot*1000/sumgene
        res = pd.DataFrame([[c_tot,c_mwh_produced]], columns = ["COST (billion euros)", "Cost per MWh produced (euros/MWh)"])
        return res
        
    def write_results(self, model_name):
        print("Ecriture des résultats ..." )
        hourly_file = model_name + "_hourly_generation.csv"
        
        with open(hourly_file,"w",newline="") as hourly:
            hourly_writer = csv.writer(hourly)

            hourly_header = ["hour"]
            for tec in self.model.tec:
                hourly_header.append(tec)

            for stor in self.model.str: 
                hourly_header.append("Storage " + stor)

            for stor in self.model.str: 
                hourly_header.append("Stored " + stor)

            for rsv in self.model.frr:
                hourly_header.append("reserve " + rsv)
            hourly_header.append("Electricity demand")
            hourly_writer.writerow(hourly_header)


            for hour in self.model.h:
                hourly_data = [hour]

                # Génération
                for tec in self.model.tec:
                    hourly_data.append(round(pyo.value(self.model.gene[tec,hour]),2))

                # Stockage
                for storage_tecs in self.model.str:
                    hourly_data.append(-round(pyo.value(self.model.storage[storage_tecs,hour]),2))

                # Stored
                for storage_tecs in self.model.str:
                    hourly_data.append(round(pyo.value(self.model.stored[storage_tecs,hour]),2))

                # Reserve
                for frr in self.model.frr:
                    hourly_data.append(round(pyo.value(self.model.reserve[frr,hour]),2))

                hourly_data.append(round(self.demand_2050[hour],2))
                hourly_writer.writerow(hourly_data)
                
            print("Simulation du modèle faite avec succès ! ")
        return pd.read_csv(hourly_file) 

        
        
        
        
