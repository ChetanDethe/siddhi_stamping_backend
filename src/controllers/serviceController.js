//controllers/serviceController.js
const pool = require('../config/db');
const svc = require('../utils/serviceCtl');

exports.status = async (req, res) => {
  try {
    // 1. GET PROCESS STATUS (Instant from Memory)
    const running = svc.getRunningState();

    // 2. GET DB STATUS (Fast via Index)
    // Since we indexed CRTD, this is lightning fast (~1-5ms)
    const [rows] = await pool.query(
      'SELECT DATE_FORMAT(MAX(CRTD), "%Y-%m-%d %H:%i:%s.%f") AS lastReadingAt FROM bluetooth_sensor_value'
    );

    res.json({
      running,
      lastReadingAt: rows[0]?.lastReadingAt || null
    });

  } catch (e) {
    console.error('Status API Error:', e.message);
    res.status(500).json({ running: false, error: 'status error' });
  }
};

// Your dialsStatus is already optimized, keep it as is.
const { getDialStatusWithCache } = require('../utils/bluetoothChecker');

exports.dialsStatus = async (req, res) => {
  try {
     const statusData = await getDialStatusWithCache();
     res.json({ success: true, data: { dials: statusData.dials } });
  } catch(e) {
     res.status(500).json({ success: false, data: null });
  }
};