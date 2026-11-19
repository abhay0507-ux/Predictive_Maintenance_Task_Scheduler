-- =====================================================================
--  PREDICTIVE MAINTENANCE TASK SCHEDULER  -  DATABASE SCHEMA (MySQL 8 / MariaDB 10.5+)
--  DBMS concepts covered: 3NF design, PK/FK/CHECK/UNIQUE, indexes, views,
--  triggers, stored procedures, transactions, row locking, audit trail.
-- =====================================================================
DROP DATABASE IF EXISTS predictive_maintenance;
CREATE DATABASE predictive_maintenance CHARACTER SET utf8mb4;
USE predictive_maintenance;

-- ---------- 1. USERS (authentication + RBAC) ----------
CREATE TABLE users (
    user_id       INT AUTO_INCREMENT PRIMARY KEY,
    full_name     VARCHAR(80)  NOT NULL,
    email         VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          ENUM('admin','manager','technician','user') NOT NULL DEFAULT 'user',
    technician_id INT NULL,
    is_active     TINYINT(1) NOT NULL DEFAULT 1,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ---------- 2. MACHINES ----------
CREATE TABLE machines (
    machine_id   INT AUTO_INCREMENT PRIMARY KEY,
    machine_name VARCHAR(80) NOT NULL UNIQUE,
    location     VARCHAR(80) NOT NULL DEFAULT 'Plant-1',
    criticality  TINYINT NOT NULL DEFAULT 3 CHECK (criticality BETWEEN 1 AND 5),
    specialization_needed VARCHAR(40) NOT NULL DEFAULT 'Mechanical',
    status       ENUM('Running','Under Maintenance','Stopped') NOT NULL DEFAULT 'Running',
    installed_on DATE NULL
) ENGINE=InnoDB;

-- ---------- 3. TECHNICIANS ----------
CREATE TABLE technicians (
    technician_id   INT AUTO_INCREMENT PRIMARY KEY,
    technician_name VARCHAR(80) NOT NULL,
    specialization  VARCHAR(40) NOT NULL,
    availability    ENUM('Available','Busy','On Leave') NOT NULL DEFAULT 'Available',
    skill_level     TINYINT NOT NULL DEFAULT 1 CHECK (skill_level BETWEEN 1 AND 5)
) ENGINE=InnoDB;
ALTER TABLE users ADD CONSTRAINT fk_user_tech
    FOREIGN KEY (technician_id) REFERENCES technicians(technician_id) ON DELETE SET NULL;

-- ---------- 4. SPARE PARTS + which part each machine needs (M:N resolved) ----------
CREATE TABLE spare_parts (
    part_id          INT AUTO_INCREMENT PRIMARY KEY,
    part_name        VARCHAR(60) NOT NULL UNIQUE,
    quantity         INT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    minimum_quantity INT NOT NULL DEFAULT 2 CHECK (minimum_quantity >= 0),
    unit_cost        DECIMAL(10,2) NOT NULL DEFAULT 0
) ENGINE=InnoDB;

CREATE TABLE machine_parts (               -- bridge table (M:N)
    machine_id    INT NOT NULL,
    part_id       INT NOT NULL,
    qty_required  INT NOT NULL DEFAULT 1 CHECK (qty_required > 0),
    PRIMARY KEY (machine_id, part_id),
    FOREIGN KEY (machine_id) REFERENCES machines(machine_id) ON DELETE CASCADE,
    FOREIGN KEY (part_id)    REFERENCES spare_parts(part_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------- 5. SENSOR READINGS ----------
CREATE TABLE sensor_readings (
    reading_id           INT AUTO_INCREMENT PRIMARY KEY,
    machine_id           INT NOT NULL,
    temperature          FLOAT NOT NULL,
    vibration            FLOAT NOT NULL,
    pressure             FLOAT NOT NULL,
    runtime              FLOAT NOT NULL,
    failure_prediction   TINYINT NOT NULL,
    failure_risk_percent FLOAT NOT NULL,
    priority_score       FLOAT NULL,
    maintenance_priority VARCHAR(20) NULL,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (machine_id) REFERENCES machines(machine_id) ON DELETE CASCADE,
    INDEX idx_sr_machine_time (machine_id, created_at),
    INDEX idx_sr_priority (priority_score)
) ENGINE=InnoDB;

-- ---------- 6. MAINTENANCE JOBS ----------
CREATE TABLE maintenance_jobs (
    job_id                INT AUTO_INCREMENT PRIMARY KEY,
    machine_id            INT NOT NULL,
    technician_id         INT NULL,
    part_id               INT NULL,
    priority_score        FLOAT NOT NULL,
    repair_hours          INT NOT NULL DEFAULT 2 CHECK (repair_hours > 0),
    required_specialization VARCHAR(40) NULL,
    description           VARCHAR(255) NULL,
    status ENUM('Pending','Scheduled','In Progress','Completed','Cancelled') NOT NULL DEFAULT 'Pending',
    scheduled_at          DATETIME NULL,
    started_at            DATETIME NULL,
    completed_at          DATETIME NULL,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (machine_id)    REFERENCES machines(machine_id),
    FOREIGN KEY (technician_id) REFERENCES technicians(technician_id) ON DELETE SET NULL,
    FOREIGN KEY (part_id)       REFERENCES spare_parts(part_id)       ON DELETE SET NULL,
    INDEX idx_job_status_priority (status, priority_score),
    INDEX idx_job_tech (technician_id)
) ENGINE=InnoDB;

-- ---------- 7. SCHEDULER RUN HISTORY (OS algorithm comparisons) ----------
CREATE TABLE scheduler_runs (
    run_id       INT AUTO_INCREMENT PRIMARY KEY,
    algorithm    VARCHAR(30) NOT NULL,
    quantum      INT NULL,
    avg_waiting  FLOAT NOT NULL,
    avg_turnaround FLOAT NOT NULL,
    avg_response FLOAT NOT NULL,
    context_switches INT NOT NULL DEFAULT 0,
    created_by   INT NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ---------- 8. AUDIT LOG (filled only by triggers) ----------
CREATE TABLE audit_log (
    audit_id    INT AUTO_INCREMENT PRIMARY KEY,
    table_name  VARCHAR(40) NOT NULL,
    record_id   INT NOT NULL,
    action      VARCHAR(20) NOT NULL,
    old_value   VARCHAR(255) NULL,
    new_value   VARCHAR(255) NULL,
    changed_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_audit_time (changed_at)
) ENGINE=InnoDB;

-- ---------- 9. SPARE-PART RESTOCK ALERTS (filled by trigger) ----------
CREATE TABLE stock_alerts (
    alert_id   INT AUTO_INCREMENT PRIMARY KEY,
    part_id    INT NOT NULL,
    message    VARCHAR(150) NOT NULL,
    resolved   TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (part_id) REFERENCES spare_parts(part_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- =====================================================================
--  TRIGGERS
-- =====================================================================
DELIMITER $$

-- T1: audit every job status change
CREATE TRIGGER trg_job_status_audit AFTER UPDATE ON maintenance_jobs
FOR EACH ROW
BEGIN
    IF OLD.status <> NEW.status THEN
        INSERT INTO audit_log(table_name, record_id, action, old_value, new_value)
        VALUES ('maintenance_jobs', NEW.job_id, 'STATUS_CHANGE', OLD.status, NEW.status);
    END IF;
END$$

-- T2: keep technician availability + machine status consistent with job status
CREATE TRIGGER trg_job_sync_state AFTER UPDATE ON maintenance_jobs
FOR EACH ROW
BEGIN
    IF OLD.status <> NEW.status THEN
        IF NEW.status = 'In Progress' THEN
            UPDATE machines SET status='Under Maintenance' WHERE machine_id = NEW.machine_id;
            IF NEW.technician_id IS NOT NULL THEN
                UPDATE technicians SET availability='Busy' WHERE technician_id = NEW.technician_id;
            END IF;
        ELSEIF NEW.status IN ('Completed','Cancelled') THEN
            UPDATE machines SET status='Running' WHERE machine_id = NEW.machine_id;
            IF NEW.technician_id IS NOT NULL THEN
                UPDATE technicians SET availability='Available' WHERE technician_id = NEW.technician_id;
            END IF;
        END IF;
    END IF;
END$$

-- T3: low stock alert whenever quantity drops to/below the minimum
CREATE TRIGGER trg_low_stock AFTER UPDATE ON spare_parts
FOR EACH ROW
BEGIN
    IF NEW.quantity <= NEW.minimum_quantity AND OLD.quantity > NEW.quantity THEN
        INSERT INTO stock_alerts(part_id, message)
        VALUES (NEW.part_id, CONCAT('Low stock: ', NEW.part_name, ' has only ', NEW.quantity, ' left'));
    END IF;
END$$

-- T4: validate sensor readings (reject physically impossible values)
CREATE TRIGGER trg_sensor_validate BEFORE INSERT ON sensor_readings
FOR EACH ROW
BEGIN
    IF NEW.temperature < -50 OR NEW.temperature > 400 OR NEW.vibration < 0 OR NEW.pressure < 0 OR NEW.runtime < 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Invalid sensor values rejected';
    END IF;
END$$

-- T5: a technician cannot be assigned to a job if they are On Leave
CREATE TRIGGER trg_assign_validate BEFORE UPDATE ON maintenance_jobs
FOR EACH ROW
BEGIN
    DECLARE t_avail VARCHAR(20);
    IF NEW.technician_id IS NOT NULL AND (OLD.technician_id IS NULL OR OLD.technician_id <> NEW.technician_id) THEN
        SELECT availability INTO t_avail FROM technicians WHERE technician_id = NEW.technician_id;
        IF t_avail = 'On Leave' THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Technician is On Leave';
        END IF;
    END IF;
END$$

-- =====================================================================
--  STORED PROCEDURES  (transactions + row-level locking)
-- =====================================================================

-- P1: atomically reserve spare part for a job (SELECT ... FOR UPDATE prevents lost update / over-allocation)
CREATE PROCEDURE sp_reserve_part(IN p_job_id INT, OUT p_result VARCHAR(40))
BEGIN
    DECLARE v_machine INT; DECLARE v_part INT; DECLARE v_need INT; DECLARE v_qty INT;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; SET p_result = 'ERROR'; END;
    START TRANSACTION;
    SELECT machine_id INTO v_machine FROM maintenance_jobs
        WHERE job_id = p_job_id AND part_id IS NULL FOR UPDATE;
    SELECT part_id, qty_required INTO v_part, v_need FROM machine_parts
        WHERE machine_id = v_machine LIMIT 1;
    IF v_part IS NULL THEN
        SET p_result = 'NO_PART_MAPPED'; ROLLBACK;
    ELSE
        SELECT quantity INTO v_qty FROM spare_parts WHERE part_id = v_part FOR UPDATE;
        IF v_qty >= v_need THEN
            UPDATE spare_parts SET quantity = quantity - v_need WHERE part_id = v_part;
            UPDATE maintenance_jobs SET part_id = v_part WHERE job_id = p_job_id;
            SET p_result = 'ALLOCATED'; COMMIT;
        ELSE
            SET p_result = 'OUT_OF_STOCK'; ROLLBACK;
        END IF;
    END IF;
END$$

-- P2: complete a job in a single ACID transaction
CREATE PROCEDURE sp_complete_job(IN p_job_id INT)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
    START TRANSACTION;
    UPDATE maintenance_jobs SET status='Completed', completed_at=NOW()
        WHERE job_id = p_job_id AND status IN ('Scheduled','In Progress');
    COMMIT;
END$$

-- P3: restock a part
CREATE PROCEDURE sp_restock(IN p_part_id INT, IN p_qty INT)
BEGIN
    START TRANSACTION;
    UPDATE spare_parts SET quantity = quantity + p_qty WHERE part_id = p_part_id;
    UPDATE stock_alerts SET resolved = 1
        WHERE part_id = p_part_id
          AND resolved = 0
          AND (SELECT quantity > minimum_quantity FROM spare_parts WHERE part_id = p_part_id);
    COMMIT;
END$$

DELIMITER ;

-- =====================================================================
--  VIEWS  (reporting layer)
-- =====================================================================
CREATE VIEW v_latest_reading AS
SELECT sr.* FROM sensor_readings sr
JOIN (SELECT machine_id, MAX(reading_id) AS latest_id FROM sensor_readings GROUP BY machine_id) l
  ON sr.reading_id = l.latest_id;

CREATE VIEW v_machine_health AS
SELECT m.machine_id, m.machine_name, m.location, m.criticality, m.specialization_needed, m.status,
       lr.failure_risk_percent, lr.priority_score, lr.maintenance_priority, lr.created_at AS last_reading
FROM machines m LEFT JOIN v_latest_reading lr ON lr.machine_id = m.machine_id;

CREATE VIEW v_job_details AS
SELECT mj.job_id, mj.machine_id, m.machine_name, mj.technician_id, t.technician_name,
       mj.part_id, sp.part_name, mj.priority_score, mj.repair_hours, mj.required_specialization,
       mj.description, mj.status, mj.scheduled_at, mj.started_at, mj.completed_at, mj.created_at
FROM maintenance_jobs mj
JOIN machines m ON m.machine_id = mj.machine_id
LEFT JOIN technicians t ON t.technician_id = mj.technician_id
LEFT JOIN spare_parts sp ON sp.part_id = mj.part_id;

CREATE VIEW v_technician_workload AS
SELECT t.technician_id, t.technician_name, t.specialization, t.availability,
       COUNT(CASE WHEN mj.status IN ('Scheduled','In Progress') THEN 1 END) AS active_jobs,
       COUNT(CASE WHEN mj.status = 'Completed' THEN 1 END) AS completed_jobs
FROM technicians t LEFT JOIN maintenance_jobs mj ON mj.technician_id = t.technician_id
GROUP BY t.technician_id, t.technician_name, t.specialization, t.availability;

CREATE VIEW v_inventory_status AS
SELECT part_id, part_name, quantity, minimum_quantity, unit_cost,
       (quantity <= minimum_quantity) AS low_stock, quantity * unit_cost AS stock_value
FROM spare_parts;

-- =====================================================================
--  SEED DATA
-- =====================================================================
INSERT INTO technicians(technician_name, specialization, skill_level) VALUES
 ('Rahul Sharma','Mechanical',5),('Anita Verma','Electrical',4),('Vikram Singh','Hydraulic',4),
 ('Priya Nair','Mechanical',3),('Karan Mehta','Electrical',2),('Sneha Rao','Hydraulic',3);

INSERT INTO machines(machine_name, location, criticality, specialization_needed, installed_on) VALUES
 ('CNC Lathe','Plant-1',5,'Mechanical','2019-03-14'),('Conveyor Belt A','Plant-1',3,'Mechanical','2020-06-01'),
 ('Hydraulic Press','Plant-2',4,'Hydraulic','2018-11-20'),('Air Compressor','Plant-2',2,'Mechanical','2021-01-10'),
 ('Welding Robot','Plant-3',5,'Electrical','2022-08-05'),('Industrial Chiller','Plant-3',3,'Electrical','2020-02-17');

INSERT INTO spare_parts(part_name, quantity, minimum_quantity, unit_cost) VALUES
 ('Bearing',6,2,850.00),('Motor Belt',4,2,420.00),('Hydraulic Seal',3,1,1300.00),
 ('Cooling Fan',2,1,990.00),('Servo Motor',1,1,18500.00);

INSERT INTO machine_parts(machine_id, part_id, qty_required) VALUES
 (1,1,1),(2,2,1),(3,3,1),(4,4,1),(5,5,1),(6,4,1);
