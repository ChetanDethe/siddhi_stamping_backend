const pool = require('../config/db');
const q = require('../db/queries');
const svc = require('../utils/serviceCtl');
const { checkAllDialsStatus } = require('../utils/bluetoothChecker');



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


// In your backend serviceController.js, modify the response
exports.dialsStatus = async (req, res) => {
  try {
    const statusData = await checkAllDialsStatus();
    
    // Send minimal data - only MAC and connected status
    const minimalResponse = {
      success: true,
      data: {
        dials: statusData.dials.map(dial => ({
          mac: dial.mac,
          connected: dial.connected
        }))
      }
    };
    
    res.json(minimalResponse);
  } catch (error) {
    res.status(500).json({
      success: false,
      data: null
    });
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