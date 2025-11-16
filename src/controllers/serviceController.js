const pool = require('../config/db');
const q = require('../db/queries');
const svc = require('../utils/serviceCtl');

exports.status = async (req, res) => {
  try {
    // <-- Use isRunning(), NOT start()
    const running = await svc.isRunning();  

    const [rows] = await pool.query(
      'SELECT DATE_FORMAT(MAX(CRTD), "%Y-%m-%d %H:%i:%s.%f") AS lastReadingAt FROM bluetooth_sensor_value'
    );

    res.json({
      running,
      lastReadingAt: rows[0]?.lastReadingAt || null
    });

  } catch (e) {
    res.status(500).json({ running: false, error: 'status error' });
  }
};


// exports.start = async (req, res) => {
//   try {
//     const running = await svc.start();
//     if (!running) return res.status(500).json({ running: false, error: 'Failed to start' });
//     res.json({ running: true });
//   } catch (e) {
//     console.error('start error:', e);
//     res.status(500).json({ error: 'start error' });
//   }
// };

// exports.stop = async (req, res) => {
//   try {
//     const running = await svc.stop();
//     res.json({ running });
//   } catch (e) {
//     console.error('stop error:', e);
//     res.status(500).json({ error: 'stop error' });
//   }
// };