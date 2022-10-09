# evm_lib_controllers
# Energy Manager Controller Classes
# D. Zogg, 11.05.2022

# TODO for all controllers: reserve power for waiting components!
# TODO test logic in real applications!

class controller():
    # base class for controller

    def __init__(self, name:str):
        self.name = name           # name of controller (string)
        self.type = None           # type of controller
        self.signal = 0            # controller signal (process value)
        self.output = 0            # controller output (continuous)
        self.mode = 0              # controller mode (0 = off, 1 = on, 2 = high, etc.)
 
    def get_type(self):
        return self.type

    def calc_output(self):
        self.output = 0
        self.mode = 0
        return [self.mode, self.output, None]
        

class excess_controller(controller):
    # class for pv excess controller
    # excess = total_production - total_consumption
    # switch on when excess > limit

    def __init__(self, name:str):
        super().__init__(name)
        self.type = 'excess_controller'
        self.limit = 0
    
    def set_limit(self, limit:float):     # set limit
        self.limit = limit

    def calc_output(self, total_production:float, total_consumption:float, own_consumption:float):
        # input total_production: sum of production of all pv plants (kW)
        # input total_consumption: sum of consumption of all devices (kw)
        # input own_consumption: consumption of specific device which is to be controlled (kW)
        # output mode: on(1) or off(0)
        # output output: continuous controller output = excess (kW) 

        remaining_consumption = total_consumption - own_consumption  # remaining consumption without own device
        excess = total_production - remaining_consumption             # pv excess

        if excess > self.limit:              
            self.mode = 1                    # switch on
            self.output = excess             # output = pv excess
        else:
            self.mode = 0                    # switch off
            self.output = 0                  # output = 0

        return [self.mode, self.output, excess]      # return mode, output and excess as list

class stepwise_excess_controller(controller):
    # class for pv excess controller with stepwise output
    # excess = total_production - total_consumption
    # switch steps according to excess and limits, steps = 0 (off), 1, 2, 3, ...

    def __init__(self, name:str):
        super().__init__(name)
        self.type = 'stepwise_excess_controller'
    
    def set_limits(self, limits_list:float):     # set limit
        self.limits_lists = limits_list            # list of limits [limit0, limit1, limit2] (kW) for each step

    def calc_output(self, total_production:float, total_consumption:float, own_consumption:float):
        # input total_production: sum of production of all pv plants (kW)
        # input total_consumption: sum of consumption of all devices (kw)
        # input own_consumption: consumption of specific device which is to be controlled (kW)
        # output mode: step 0 (off), 1, 2, 3, ...
        # output output: continuous controller output = excess (kW) 

        consumption_remain = consumption_total - own_consumption  # remaining consumption without own device
        excess = production_total - consumption_total             # pv excess

        i = 0
        self.mode = 0                   # mode 0 = off
        for limit in self.limits_list:
            i += 1
            if excess > limit:              
                self.mode = i                    # set mode to step i (1, 2, 3, ...)
        
        self.output = excess

        return [self.mode, self.output, excess]      # return mode, output and excess as list


class coverage_controller(controller):
    # class for pv coverage controller
    # excess = total_production - total_consumption
    # coverage = excess / own_consumption
    # switch on when coverage > limit

    def __init__(self, name:str):
        super().__init__(name)
        self.type = 'coverage_controller'
    
    def set_limit(self, limit:float):     # set limit
        self.limit = limit

    def calc_output(self, total_production:float, total_consumption:float, own_consumption:float):
        # input total_production: sum of production of all pv plants (kW)
        # input total_consumption: sum of consumption of all devices (kw)
        # input own_consumption: consumption of specific device which is to be controlled (kW)
        # output mode: on(1) or off(0)
        # output output: over coverage = coverage - 1 (continuous signal 0..x)

        remain_consumption = total_consumption - own_consumption  # remaining consumption without own device
        excess = total_production - remain_consumption             # pv excess
        if own_consumption > 0:
            coverage = excess / own_consumption                       # pv coverage of own device
        else:
            coverage = 0

        if coverage > self.limit:              
            self.mode = 1                    # switch on
            self.output = coverage-1         # output = over coverage
        else:
            self.mode = 0                    # switch off
            self.output = 0                  # output = 0

        return [self.mode, self.output, coverage]      # return mode, output and coverage as list
    
class adaptive_coverage_controller(coverage_controller):
    # class for pv coverage controller
    # excess = total_production - total_consumption
    # coverage = excess / own_consumption
    # switch on when coverage > limit

    def __init__(self, name:str):
        super().__init__(name)
        self.type = 'adaptive_coverage_controller'
    
    def calc_limit(self, max_production:float, mean_own_consumption:float, x:float=0.5):     # set maximum pv production
        # calculate limit from max pv production
        # input max_production: max pv production of the actual day (from meteo or last day)
        # input mean_own_consumption: mean consumption of own device
        # input x: set limit to x% of max coverage (x = number in range 0..1, default = 0.5)
        
        max_excess = max_production - mean_own_consumption            # expected max pv excess of the day
        max_coverage = excess / own_consumption                       # expected max pv coverage of own device
        self.limit = x * max_coverage                                 # set limit to x% of max coverage

class price_controller(controller):
    # class for price controller
    # production price calculated from pv coverage and solar/grid tarifs
    # consumption price calculated from state of consumer (e.g. temperature for thermal systems)
    # controller is switched on when consumption price is higher than production price
    # continuous controller is driven by price difference
    
    def __init__(self, name:str):
        super().__init__(name)
        self.type = 'price_controller'
    
    def set_params(self, min_state:float, max_state:float, solar_tarif:float, grid_tarif:float):     # set parameters
        self.min_state = min_state                  # minimum loading state of consumer (e.g. minimum temperature)
        self.max_state = max_state                   # maximum loading state of consumer (e.g. maximum temperature)
        self.solar_tarif = solar_tarif              # solar tarif (ct/kWh)
        self.grid_tarif = grid_tarif                # grid tarif (ct/kWh)         

    def calc_output(self, state:float, total_production:float, max_production:float, total_consumption:float, mean_consumption:float, own_consumption:float, own_mean_consumption:float, adaptive:bool):
        # input state: loading state of device (e.g. temperature)
        # input total_production: sum of production of all pv plants (kW)
        # input max_production: expected peak production of day (used for adaptive = true)
        # input total_consumption: sum of consumption of all devices (kw)
        # input mean_consumption: expected mean consumption of all devices (used for adaptive = true)
        # input own_consumption: consumption of specific device which is to be controlled (kW)
        # input own_mean_consumption: mean consumption of specific device if it is switched on (kW)
        # input adaptive: adaption of consumption price if true 
        # output mode: on(1) or off(0)
        # output output: continuous signal -1..0..1

         # correction of total consumption with own consumption -> eliminates self switching
        if own_consumption > 0:
            consumption_corr = total_consumption
        else:
            consumption_corr = total_consumption + own_mean_consumption    

        coverage = total_production / total_consumption           # total solar coverage
        if coverage > 1: coverage = 1                             # limit coverage to max 1

        # calculation of production price
        production_price = self.solar_tarif*coverage + self.grid_tarif*(1-coverage)    # linear interpolation between solar and grid tarif

        # calculation of consumption price
        max_price = self.grid_tarif          # set maximum price to grid tarif (assuming that grid_tarif > solar_tarif)
        if adaptive:
            max_coverage = max_production / mean_consumption        # expected max pv coverage
            if max_coverage > 1: max_coverage = 1
            min_price = self.solar_tarif*max_coverage + self.grid_tarif*(1-max_coverage) # adaptive min price
        else:
            min_price = self.solar_tarif         # absolute min price

        consumption_price = max_price-(max_price-min_price)/(self.max_state-self.min_state)*(state-self.min_state) # linear interpolation

        # calculate outputs based on price difference
        if consumption_price > production_price:              
            self.mode = 1                    # switch on
        else:
            self.mode = 0                    # switch off

        self.output = (consumption_price-production_price)/(max_price-min_price)   # output scaled price difference
        
        return [self.mode, self.output, (consumption_price, production_price)]      # return mode, output and prices as list    

   