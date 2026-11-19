-- =====================================================================
--  DEMO QUERIES  (Member 3 - queries, views, analytics)   mysql -u root -p predictive_maintenance < queries.sql
-- =====================================================================
USE predictive_maintenance;

-- 1. JOIN across 4 tables: full job sheet
SELECT j.job_id, m.machine_name, t.technician_name, sp.part_name, j.priority_score, j.status
FROM maintenance_jobs j
JOIN machines m ON m.machine_id = j.machine_id
LEFT JOIN technicians t ON t.technician_id = j.technician_id
LEFT JOIN spare_parts sp ON sp.part_id = j.part_id
ORDER BY j.priority_score DESC;

-- 2. Aggregate + GROUP BY + HAVING: technicians who finished more than one job
SELECT t.technician_name, COUNT(*) AS finished
FROM maintenance_jobs j JOIN technicians t USING (technician_id)
WHERE j.status = 'Completed' GROUP BY t.technician_id, t.technician_name HAVING COUNT(*) > 1;

-- 3. Window function: RANK of machines by risk inside each plant
SELECT machine_name, location, failure_risk_percent,
       RANK() OVER (PARTITION BY location ORDER BY failure_risk_percent DESC) AS plant_rank
FROM v_machine_health WHERE failure_risk_percent IS NOT NULL;

-- 4. Window function: moving average of the last 3 readings (trend smoothing)
SELECT machine_id, reading_id, failure_risk_percent,
       ROUND(AVG(failure_risk_percent) OVER (PARTITION BY machine_id ORDER BY reading_id
             ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS moving_avg
FROM sensor_readings;

-- 5. Window function LAG: change in risk since the previous reading
SELECT machine_id, reading_id, failure_risk_percent,
       failure_risk_percent - LAG(failure_risk_percent) OVER (PARTITION BY machine_id ORDER BY reading_id) AS delta
FROM sensor_readings;

-- 6. Correlated subquery: machines whose latest risk is above the plant average
SELECT m.machine_name, v.failure_risk_percent
FROM v_machine_health v JOIN machines m USING (machine_id)
WHERE v.failure_risk_percent > (SELECT AVG(failure_risk_percent) FROM v_machine_health);

-- 7. NOT EXISTS (relational division flavour): machines that never had a maintenance job
SELECT machine_name FROM machines m
WHERE NOT EXISTS (SELECT 1 FROM maintenance_jobs j WHERE j.machine_id = m.machine_id);

-- 8. CTE: average resolution time per technician
WITH done AS (
  SELECT technician_id, TIMESTAMPDIFF(MINUTE, created_at, completed_at) AS mins
  FROM maintenance_jobs WHERE status = 'Completed')
SELECT t.technician_name, ROUND(AVG(mins) / 60, 2) AS avg_hours
FROM done JOIN technicians t USING (technician_id) GROUP BY t.technician_name;

-- 9. Index usage: the optimiser should pick idx_job_status_priority
EXPLAIN SELECT job_id FROM maintenance_jobs WHERE status = 'Pending' ORDER BY priority_score DESC;

-- 10. Views
SELECT * FROM v_technician_workload;
SELECT * FROM v_inventory_status WHERE low_stock = 1;
