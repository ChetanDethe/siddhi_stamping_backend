module.exports = {
  SELECT_MAPPINGS: 'SELECT mac, equipmentName, updated_at FROM mac_equipment_map ORDER BY mac ASC',
  UPSERT_MAPPING: 'INSERT INTO mac_equipment_map (mac, equipmentName) VALUES (?, ?) ON DUPLICATE KEY UPDATE equipmentName = VALUES(equipmentName)',
  SELECT_LATEST_READINGS: `SELECT device_mac, equipmentName, value, 
                                  DATE_FORMAT(CRTD, '%Y-%m-%d %H:%i:%s.%f') AS CRTD
                           FROM bluetooth_sensor_value
                           ORDER BY CRTD DESC
                           LIMIT ?`,
  SELECT_LAST_READING_AT: 'SELECT DATE_FORMAT(MAX(CRTD), "%Y-%m-%d %H:%i:%s.%f") AS lastReadingAt FROM bluetooth_sensor_value',
};