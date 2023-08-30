# Generative AI was used for some Code
import pandas as pd
import matplotlib.pyplot as plt
from datetime import timedelta

# path to device logging data
data = pd.read_csv('_logFiles/DeviceLog.log', delimiter=';')
# used speed up factor for creating data
speed_up_factor = 1

# convert the timestamp column to a datetime object
data['timestamp'] = pd.to_datetime(data['timestamp'], format="%d.%m.%y %H:%M:%S")

# calculate the minimum timestamp
min_timestamp = data['timestamp'].min()

# subtract the minimum timestamp from all timestamps
data['timestamp'] = ((data['timestamp'] - min_timestamp)*speed_up_factor)/pd.Timedelta(hours=1)

# group the data by name
grouped = data.groupby('name')

# List of names to exclude from the plot
exclude_names = ['global_total_consumption_plus_reserved', 'global_total_power_reserved', 'global_total_production', "Hausanschluss", "global_total_consumption"]
exclude_names_for_power = ["consumption_price_Elektroheizung"]  # excluded in the first plot, will be shown in the second plot (priceController prices)

# configure color of plots
device_colors = {
    'Elektroheizung': 'tab:blue',
    'PV-Anlage Garage': 'tab:green',
    'global_total_consumption': 'tab:purple',
    'REMAINING_CONSUMPTION': 'tab:red',
    'WALLBE_ECO_S': 'tab:olive'
}

# create a new plot with twin y-axes
fig, ax1 = plt.subplots()
ax2 = ax1.twinx()
lines_power = []
lines_temp = []

# second plot for consumption/production prices
fig2, ax3 = plt.subplots()


# plot each group on the same plot, excluding names in the exclude_names list
for name, group in grouped:
    if name not in exclude_names:
        if name not in exclude_names_for_power:
            color = device_colors.get(name, "black")
            group.plot(x='timestamp', y='power', ax=ax1, label=f"{name}", linewidth=2,legend=False,color=color)
        if group['room_temp'].notna().any():
            group.plot(x='timestamp', y='room_temp', ax=ax2, label=f"{name} temp", linestyle="--",legend=False)
        if group["consumption_price"].notna().any():
            group.plot(x='timestamp', y='consumption_price', ax=ax3, label=f"consumption price", linestyle="-", legend=True)
            group.plot(x='timestamp', y='production_price', ax=ax3, label=f"production price", linestyle="-", legend=True)

# Add a horizontal dashed line at power = 6 kW
#ax1.axhline(y=6, color='orange', linestyle='--', label='Deckungsgrad-Limite (6 kW)')

# create one legend with names of plots
handles1, labels1 = ax1.get_legend_handles_labels()
handles2, labels2 = ax2.get_legend_handles_labels()
handles = handles1 + handles2
labels = labels1 + labels2
fig.legend(handles, labels)

# set the x-axis label to 'Time' and the y-axis labels to 'Power [kW]' and 'Temperature [Celsius]'
ax1.set_xlabel('Time [h]')
ax1.set_ylabel('Power [kW]')
ax2.set_ylabel('Temperature [Celsius]')
# for consumption price plot
ax3.set_xlabel('Time [h]')
ax3.set_ylabel('Price [rp/kWh]')


# save plots
fig.savefig('Plot.png', dpi=300)
fig2.savefig('Plot_Prices.png', dpi=300)


# display the plot
plt.show()
