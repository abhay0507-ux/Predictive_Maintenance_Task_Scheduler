-- =====================================================================
--  MANUAL CONCURRENCY DEMO  (Member 2)   - open TWO mysql terminals
-- =====================================================================
USE predictive_maintenance;
-- Terminal A:
START TRANSACTION;
SELECT quantity FROM spare_parts WHERE part_name='Bearing' FOR UPDATE;   -- takes a row lock
-- (do NOT commit yet)

-- Terminal B:
START TRANSACTION;
SELECT quantity FROM spare_parts WHERE part_name='Bearing' FOR UPDATE;   -- BLOCKS, waiting for A

-- Terminal A:
UPDATE spare_parts SET quantity = quantity - 1 WHERE part_name='Bearing';
COMMIT;                                                                  -- B now continues and sees the new value

-- Terminal B:
COMMIT;

-- DEADLOCK demo (InnoDB detects it and kills one transaction):
-- A: START TRANSACTION; UPDATE spare_parts SET quantity=quantity WHERE part_name='Bearing';
-- B: START TRANSACTION; UPDATE spare_parts SET quantity=quantity WHERE part_name='Motor Belt';
-- A: UPDATE spare_parts SET quantity=quantity WHERE part_name='Motor Belt';   -- waits for B
-- B: UPDATE spare_parts SET quantity=quantity WHERE part_name='Bearing';      -- ERROR 1213 Deadlock found
SHOW ENGINE INNODB STATUS;   -- section "LATEST DETECTED DEADLOCK"
