# Generative AI was used for some Code
import logging



def update_global_controller_values(devices_list):
    total_consumption = 0
    total_production = 0
    total_max_production = 0

    for index, device in enumerate(devices_list):
        # find REMAINING_CONSUMPTION device in list
        if device.device_type == "REMAINING_CONSUMPTION":
            remaining_consumption_setting = device.device_setting
            remaining_consumption_device = device

        # find CENTRAL_POWER_METER device in list
        elif device.device_type == "CENTRAL_POWER_METER":
            if device.simulated:
                is_cpm_simulated = True
            else:
                is_cpm_simulated = False
            central_power_meter_device = device

        # calculate production anc consumption
        elif device.prosumer_type == "producer":
            total_production += device.power_sensor_power
            total_max_production += device.max_power
        elif device.prosumer_type == "consumer":
            total_consumption += device.power_sensor_power
        else:
            raise NotImplementedError

    # decision tree for calculation of remaining consumption. Remaining consumption can be simulated, calculated or measured
    if remaining_consumption_device is not None:
        if is_cpm_simulated and remaining_consumption_setting == "SIMULATED":
            remaining_consumption = round(remaining_consumption_device.power_sensor_power,4)
            total_consumption += remaining_consumption
            central_power_meter_device.power_sensor_power = round(total_consumption - total_production,4)
        elif not is_cpm_simulated and remaining_consumption_setting == "CALCULATED":
            remaining_consumption = round(central_power_meter_device.power_sensor_power + total_production - total_consumption,4)
            remaining_consumption_device.power_sensor_power = remaining_consumption
        elif not is_cpm_simulated and remaining_consumption_setting == "MEASURED":
            pass
            # both devices get measured
        else:
            raise NotImplementedError

    # update information for Controller class
    Controller.global_total_consumption = round(total_consumption, 4)
    Controller.global_total_production = round(total_production, 4)
    Controller.global_max_total_production = round(total_max_production)

    return total_consumption, total_production


class Controller:
    # base class for controller

    # global_values in kW
    global_total_consumption = 0
    global_total_production = 0
    global_max_total_production = 0
    global_power_reserved = 0

    def __init__(self, OpenCEM_id: str = ""):
        self.type = None  # type of controller
        self.signal = 0  # controller signal (process value)
        self.output = 0  # controller output (continuous)
        self.mode = 0  # controller mode (0 = off, 1 = on, 2 = high, etc.)
        self.device = None
        self.OpenCEM_id = OpenCEM_id

    def get_type(self):
        return self.type

    def calc_output(self):
        self.output = 0
        self.mode = 0
        return [self.mode, self.output, None]

    def set_device(self, device_obj):
        if self.device is None:
            self.device = device_obj
        else:
            raise ValueError("Controller already assigned to a device.")
        return None

    @classmethod
    def log_global_power_values(cls):
        # logs global data to the device logger
        logger = logging.getLogger("device_logger")
        # global_total_consumption
        logger.info(
            f";global_total_consumption;;{cls.global_total_consumption};;;;;;")
        # global_power_reserved
        logger.info(
            f";global_total_power_reserved;;{cls.global_power_reserved};;;;;;")
        # global_total_consumption with consumption reserved
        logger.info(
            f";global_total_consumption_plus_reserved;;{cls.global_total_consumption + cls.global_power_reserved};;;;;;")
        # global_total_production
        logger.info(
            f";global_total_production;;{cls.global_total_production};;;;;;")

class ExcessController(Controller):
    # class for pv excess controller
    # excess = total_production - total_consumption
    # switch on when excess > limit

    def __init__(self, *, limit: float, OpenCEM_id : str = ""):
        super().__init__(OpenCEM_id=OpenCEM_id)
        self.type = 'excess_controller'
        self.limit = limit

    def set_limit(self, limit: float):  # set limit in kW?
        self.limit = limit

    def calc_output(self):
        # output mode: on(1) or off(0)
        # output output: continuous controller output = excess (kW) 

        remaining_consumption = (Controller.global_total_consumption + Controller.global_power_reserved) - self.device.power_sensor_power  # remaining consumption without own device
        excess = Controller.global_total_production - remaining_consumption  # pv excess

        old_mode = self.device.mode

        if excess > self.limit:
            self.mode = 1  # switch on
            self.output = excess  # output = pv excess
        else:
            self.mode = 0  # switch off
            self.output = 0  # output = 0

        # if device changes its state to "on", the nominal power will be added to global total consumption.
        if old_mode == 0 and self.mode >= 1:
            Controller.global_power_reserved += self.device.nominal_power

        return self.mode, self.output, excess  # return mode, output and excess as list


class StepwiseExcessController(Controller):
    # class for pv excess controller with stepwise output, used for devices with multiple modes
    # excess = total_production - total_consumption
    # switch steps according to excess and limits, steps = 0 (off), 1, 2, 3, ...

    def __init__(self, *, limits: list, OpenCEM_id : str = ""):
        super().__init__(OpenCEM_id=OpenCEM_id)
        self.type = 'stepwise_excess_controller'
        self.limits_list = limits

    def set_limits(self, limits_list: float):  # set limit
        self.limits_lists = limits_list  # list of limits [limit0, limit1, limit2] (kW) for each step

    def calc_output(self):
        # output mode: step 0 (off), 1, 2, 3, ...
        # output output: continuous controller output = excess (kW) 

        remaining_consumption = (Controller.global_total_consumption + Controller.global_power_reserved) - self.device.power_sensor_power  # remaining consumption without own device
        excess = Controller.global_total_production - remaining_consumption  # pv excess

        old_mode = self.device.mode

        i = 0
        self.mode = 0  # mode 0 = off
        for limit in self.limits_list:
            i += 1
            if excess > limit:
                self.mode = i  # set mode to step i (1, 2, 3, ...)

        self.output = excess

        # if device changes its state to "on", the power from the according step will be
        # added to global total consumption.
        if old_mode == 0 and self.mode >= 1:
            Controller.global_power_reserved += self.limits_list[self.mode - 1]

        return [self.mode, self.output, excess]  # return mode, output and excess as list


class coverage_controller(Controller):
    # class for pv coverage controller
    # excess = total_production - total_consumption
    # coverage = excess / own_consumption
    # switch on when coverage > limit

    def __init__(self, *, limit: float = 0, OpenCEM_id : str = ""):
        super().__init__(OpenCEM_id=OpenCEM_id)
        self.type = 'coverage_controller'
        self.limit = limit

    def set_limit(self, limit: float):  # set limit
        self.limit = limit

    def calc_output(self):
        # output mode: on(1) or off(0)
        # output output: over coverage = coverage - 1 (continuous signal 0..x)

        own_consumption = self.device.power_sensor_power  # TODO is this correct?

        remain_consumption = (Controller.global_total_consumption + Controller.global_power_reserved) - own_consumption  # remaining consumption without own device
        excess = Controller.global_total_production - remain_consumption  # pv excess

        old_mode = self.device.mode

        # pv coverage of own device
        if own_consumption > 0:
            coverage = excess / own_consumption
        else:
            coverage = excess / self.device.nominal_power

        if coverage > self.limit:
            self.mode = 1  # switch on
            self.output = coverage - 1  # output = over coverage
        else:
            self.mode = 0  # switch off
            self.output = 0  # output = 0

        # if device changes its state to "on", the nominal power will be added to global total consumption.
        if old_mode == 0 and self.mode >= 1:
            Controller.global_power_reserved += self.device.nominal_power

        return self.mode, self.output, coverage  # return mode, output and coverage as list

# adaptive controllers are not yet implemented
"""
class adaptive_coverage_controller(coverage_controller):
    # class for pv coverage controller
    # excess = total_production - total_consumption
    # coverage = excess / own_consumption
    # switch on when coverage > limit

    def __init__(self, name: str):
        super().__init__(name)
        self.type = 'adaptive_coverage_controller'

    def calc_limit(self, max_production: float, mean_own_consumption: float,
                   x: float = 0.5):  # set maximum pv production
        # calculate limit from max pv production
        # input max_production: max pv production of the actual day (from meteo or last day)
        # input mean_own_consumption: mean consumption of own device
        # input x: set limit to x% of max coverage (x = number in range 0..1, default = 0.5)

        max_excess = max_production - mean_own_consumption  # expected max pv excess of the day
        max_coverage = excess / own_consumption  # expected max pv coverage of own device
        self.limit = x * max_coverage  # set limit to x% of max coverage
"""

class PriceController(Controller):
    # class for price controller
    # production price calculated from pv coverage and solar/grid tarifs
    # consumption price calculated from state of consumer (e.g. temperature for thermal systems)
    # controller is switched on when consumption price is higher than production price
    # continuous controller is driven by price difference

    def __init__(self, *, min_state=0.0, max_state=0.0, solar_tarif=0.0, grid_tarif=0.0, is_adaptive=False, OpenCEM_id : str = ""):
        super().__init__(OpenCEM_id=OpenCEM_id)
        self.type = 'price_controller'
        self.state = 0.0  # current state
        self.min_state = min_state  # minimum loading state of consumer (e.g. minimum temperature)
        self.max_state = max_state  # maximum loading state of consumer (e.g. maximum temperature)
        self.solar_tarif = solar_tarif  # solar tarif (ct/kWh)
        self.grid_tarif = grid_tarif  # grid tarif (ct/kWh)
        self.is_adaptive = is_adaptive

    def set_params(self, min_state: float, max_state: float, solar_tarif: float, grid_tarif: float):  # set parameters
        self.min_state = min_state  # minimum loading state of consumer (e.g. minimum temperature)
        self.max_state = max_state  # maximum loading state of consumer (e.g. maximum temperature)
        self.solar_tarif = solar_tarif  # solar tarif (ct/kWh)
        self.grid_tarif = grid_tarif  # grid tarif (ct/kWh)

    def calc_output(self, state: float):
        """
        calculates mode, output, consumption price and production price of the controller
        :param state: is the current temperature
        :return:
        """


        if self.device.power_sensor_power > 0:
            consumption_corr = Controller.global_total_consumption
        else:
            if self.device.mean > 0:
                consumption_corr = Controller.global_total_consumption + self.device.mean
            else:
                consumption_corr = Controller.global_total_consumption + self.device.nominal_power

        # catch ZeroDivisionError when there is no consumption (most likely only used when simulated)
        try:
            coverage = Controller.global_total_production / consumption_corr  # total solar coverage
        except ZeroDivisionError:
            if Controller.global_total_production == 0:
                coverage = 0
            else:
                coverage = 1

        if coverage > 1:
            coverage = 1  # limit coverage to max 1

        # calculation of production price
        production_price = self.solar_tarif * coverage + self.grid_tarif * (
                1 - coverage)  # linear interpolation between solar and grid tarif

        # calculation of consumption price
        max_price = self.grid_tarif  # set maximum price to grid tarif (assuming that grid_tarif > solar_tarif)

        # adaptiv is not yet implemented in OpenCEM
        if self.is_adaptive:
            max_coverage = Controller.global_max_total_production / mean_consumption  # expected max pv coverage #Todo: max_production und mean cosuption bestimmen
            if max_coverage > 1:
                max_coverage = 1
            min_price = self.solar_tarif * max_coverage + self.grid_tarif * (1 - max_coverage)  # adaptive min price
        else:
            min_price = self.solar_tarif  # absolute min price

        consumption_price = max_price - (max_price - min_price) / (self.max_state - self.min_state) * (
                state - self.min_state)  # linear interpolation

        # calculate outputs based on price difference
        if consumption_price > production_price:
            self.mode = 1  # switch on
        else:
            self.mode = 0  # switch off

        self.output = (consumption_price - production_price) / consumption_price  # output scaled price difference
        scaled_output = self.output * self.device.nominal_power  # in kW

        # logging of the consumption and production price in the device logger
        logger = logging.getLogger("device_logger")
        logger.info(
            f";consumption_price_{self.device.name};;;;;;;;;{consumption_price};{production_price};{scaled_output}")

        return [self.mode, self.output,
                (consumption_price, production_price)]  # return mode, output and prices as list


class DynamicExcessController(Controller):

    def __init__(self, *, min_limit: float = 0, max_limit: float = 0, OpenCEM_id : str = ""):
        super().__init__(OpenCEM_id=OpenCEM_id)
        self.type = "dynamic_excess"
        self.min_limit = min_limit
        self.max_limit = max_limit

    def set_params(self, min_limit: float, max_limit: float):
        if max_limit > min_limit:
            self.min_limit = min_limit
            self.max_limit = max_limit
        else:
            raise ValueError("max must be bigger than min limit")

    def calc_output(self):

        remaining_consumption = (Controller.global_total_consumption + Controller.global_power_reserved) - self.device.power_sensor_power  # remaining consumption without own device
        excess = Controller.global_total_production - remaining_consumption  # pv excess

        old_mode = self.device.mode

        # mode will be on between the limits, output is excess between limits
        if excess > self.min_limit:
            self.mode = 1  # switch on
            if excess <= self.max_limit:
                self.output = excess  # output = pv excess
            else:
                self.output = self.max_limit
        else:
            self.mode = 0  # switch off
            self.output = 0  # output = 0

        # if device changes its state to "on", the nominal power will be added to global total consumption.
        if old_mode == 0 and self.mode >= 1:
            Controller.global_power_reserved += self.device.nominal_power

        return self.mode, self.output, excess  # return mode, output and excess as list





