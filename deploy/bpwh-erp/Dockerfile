FROM frappe/erpnext:v15.106.0

USER root

COPY apps/bp_water_heaters /home/frappe/frappe-bench/apps/bp_water_heaters
RUN chown -R frappe:frappe /home/frappe/frappe-bench/apps/bp_water_heaters

USER frappe
WORKDIR /home/frappe/frappe-bench

RUN /home/frappe/frappe-bench/env/bin/pip install --no-cache-dir -e /home/frappe/frappe-bench/apps/bp_water_heaters
RUN ln -sfn /home/frappe/frappe-bench/apps/bp_water_heaters/bp_water_heaters/public /home/frappe/frappe-bench/assets/bp_water_heaters
