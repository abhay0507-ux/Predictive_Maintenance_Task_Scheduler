-- =====================================================================
--  DATABASE-LEVEL SECURITY  (Member 4)  - principle of least privilege
--  Run as MySQL root AFTER schema.sql.   (MySQL 8 / MariaDB 10.5+)
-- =====================================================================
USE predictive_maintenance;

CREATE ROLE IF NOT EXISTS pms_readonly, pms_operator, pms_manager;

GRANT SELECT ON predictive_maintenance.v_machine_health    TO pms_readonly;
GRANT SELECT ON predictive_maintenance.v_inventory_status  TO pms_readonly;
GRANT SELECT ON predictive_maintenance.v_job_details       TO pms_readonly;

GRANT SELECT ON predictive_maintenance.* TO pms_operator;
GRANT INSERT ON predictive_maintenance.sensor_readings TO pms_operator;
GRANT UPDATE (status, started_at, completed_at) ON predictive_maintenance.maintenance_jobs TO pms_operator;

GRANT SELECT, INSERT, UPDATE ON predictive_maintenance.* TO pms_manager;
GRANT EXECUTE ON predictive_maintenance.* TO pms_manager;      -- stored procedures
-- NOTE: nobody except root may DELETE from audit_log or DROP tables.

CREATE USER IF NOT EXISTS 'viewer'@'localhost'   IDENTIFIED BY 'View@2026';
CREATE USER IF NOT EXISTS 'operator'@'localhost' IDENTIFIED BY 'Oper@2026';
CREATE USER IF NOT EXISTS 'mgr'@'localhost'      IDENTIFIED BY 'Mgr@2026';
GRANT pms_readonly TO 'viewer'@'localhost';   SET DEFAULT ROLE pms_readonly TO 'viewer'@'localhost';
GRANT pms_operator TO 'operator'@'localhost'; SET DEFAULT ROLE pms_operator TO 'operator'@'localhost';
GRANT pms_manager TO 'mgr'@'localhost';      SET DEFAULT ROLE pms_manager TO 'mgr'@'localhost';

-- (MariaDB users: write  SET DEFAULT ROLE pms_readonly FOR 'viewer'@'localhost';  instead of TO)
-- Prove it:  mysql -u viewer -p  ->  SELECT * FROM v_machine_health;  (works)
--                                    DELETE FROM machines;             (ERROR 1142 denied)
