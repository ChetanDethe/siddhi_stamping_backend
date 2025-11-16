const pool = require('../config/db');
const q = require('../db/queries');

exports.getLatest = async (req, res) => {
  try {
    let limit = parseInt(req.query.limit || '10', 10);
    if (!Number.isFinite(limit) || limit <= 0) limit = 10;
    if (limit > 100) limit = 100;
    const [rows] = await pool.query(q.SELECT_LATEST_READINGS, [limit]);
    res.json(rows);
  } catch (e) {
    console.error('getLatest error:', e);
    res.status(500).json({ error: 'DB error' });
  }
};