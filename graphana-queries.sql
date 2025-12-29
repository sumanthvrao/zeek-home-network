-- Grafana SQLite Queries for Zeek Logs
-- 
-- Usage in Grafana:
-- 1. Add a new Panel
-- 2. Select your SQLite data source
-- 3. Choose "Format as: Time series" for time-based queries
-- 4. For time series queries, Grafana will automatically detect:
--    - Time column (must be named "time" and be Unix timestamp in seconds)
--    - Metric column (the grouping dimension, e.g., host IP)
--    - Value column (the metric value)
-- 5. Adjust time intervals in queries based on your time range:
--    - Short ranges (< 1 hour): 5-60 second intervals
--    - Medium ranges (1-24 hours): 1-5 minute intervals  
--    - Long ranges (> 1 day): 5-15 minute intervals
--
-- Note: Zeek timestamps (ts) are in Unix epoch seconds
-- Grafana variables: $__from and $__to are in milliseconds, so divide by 1000

-- Outgoing traffic volume per host over time (Time Series)
-- Creates one line graph per originating host showing their traffic volume
-- Adjust interval: 60 = 1 minute, 300 = 5 minutes, 900 = 15 minutes
-- In Grafana: Format as "Time series" - will automatically create one line per host
-- Title: Outgoing traffic volume per host over time

SELECT 
  (ROUND(ts / 60) * 60) AS time,
  id_orig_h AS metric,
  SUM(orig_bytes) AS value
FROM 
  conn
WHERE 
  ts >= $__from / 1000 AND 
  ts < $__to / 1000
GROUP BY 
  time, id_orig_h
ORDER BY 
  time ASC;

-- Title: Total connections per 5 second interval
-- Total connections per 5 second interval
SELECT 
  (ROUND(ts / 5) * 5) AS time, 
  COUNT(*) AS "value"
FROM 
  conn
WHERE 
  ts >= $__from / 1000 AND 
  ts < $__to / 1000
GROUP BY 
  time
ORDER BY 
  time ASC


-- Most common DNS queries

SELECT 
  query, COUNT(*) as count
FROM dns  
WHERE ts >= $__from / 1000 AND ts < $__to / 1000
GROUP BY query
ORDER BY count DESC
LIMIT 30

-- Bytes trasferred between hosts
-- Title: Bytes Transferred / Host

SELECT id_orig_h, id_resp_h, SUM(orig_bytes) as total_orig, SUM(resp_bytes) as total_resp                                                                                                
FROM conn                                                                                                                                                      
WHERE ts >= $__from / 1000 and ts < $__to / 1000                                                                                                               
GROUP BY id_orig_h, id_resp_h                                                                                                                                  
ORDER BY total_resp DESC
LIMIT 30       

-- Total bytes sent by each originator

SELECT                                                                                                                
  id_orig_h,                                                                                                          
  sum(orig_bytes) AS total_orig_bytes                                                                                 
FROM conn                                                                                                             
WHERE ts >= ($__from / 1000) AND ts < ($__to / 1000)                                                                  
GROUP BY id_orig_h                                                                                                    
ORDER BY total_orig_bytes DESC                                                                                        
LIMIT 20;

-- Raw connections

SELECT ts, id_orig_h, id_resp_h, id_resp_p, SUM(orig_bytes) as total_orig, SUM(resp_bytes) as total_resp                                                                                                
FROM conn                                                                                                                                                      
WHERE ts >= $__from / 1000 and ts < $__to / 1000                                                                                                               
GROUP BY id_orig_h, id_resp_h                                                                                                                                  
ORDER BY ts, total_resp DESC   
