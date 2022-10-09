# Open CEM project

Open Customer Energy Manager
Smart Energy Engineering, September 2022, David Zogg

## 1) Introduction

The Open Customer Energy Manager (OpenCEM) is a project to demonstrate the functionality of SmartGridReady within a fully working energy manager. The energy manager includes all controllers required to control typical installations with pv plants, heat pumps, ev-chargers, boilers, etc.

For a detailed documentation of the Open Customer Energy Manager refer to the folder "Documentation"

## 2) Code and Libraries

The OpenCEM project consists of the following libraries and a main program:
- cem_lib_components: defines classes for components such as actuators, sensors and devices, also includes a generic smartgridready class, which encapsulates the smart grid ready functionality. The components may be simulated or connected to hardware.
- cem_lib_controllers: defines some example controller classes for local pv optimization or grid interaction
- cem_main_test: simple test program to demonstrate how to use the component and controller classes above. Note that in the current version this program is not designed to run in real time applications.



