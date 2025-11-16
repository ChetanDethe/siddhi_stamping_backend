const pool = require('../config/db');
const q = require('../db/queries');
const { MAC_RE, EQUIPMENT_LIST } = require('../constants');

function validateMapping(m) {
  return m && typeof m.mac === 'string' && typeof m.equipmentName === 'string'
    && MAC_RE.test(m.mac) && EQUIPMENT_LIST.includes(m.equipmentName);
}

exports.getMappings = async (req, res) => {
  try {
    const [rows] = await pool.query(q.SELECT_MAPPINGS);
    res.json(rows);
  } catch (e) {
    console.error('getMappings error:', e);
    res.status(500).json({ error: 'DB error' });
  }
};

exports.upsertMappings = async (req, res) => {
  try {
    const { mappings } = req.body || {};
    if (!Array.isArray(mappings) || mappings.length === 0) {
      return res.status(400).json({ error: 'mappings[] required' });
    }
    const allValid = mappings.every(validateMapping);
    if (!allValid) {
      return res.status(400).json({ error: 'Invalid mac or equipmentName' });
    }

    const conn = await pool.getConnection();
    try {
      await conn.beginTransaction();
      for (const m of mappings) {
        await conn.query(q.UPSERT_MAPPING, [m.mac, m.equipmentName]);
      }
      await conn.commit();
    } catch (err) {
      await conn.rollback();
      throw err;
    } finally {
      conn.release();
    }

    const [rows] = await pool.query(q.SELECT_MAPPINGS);
    res.json(rows);
  } catch (e) {
    console.error('upsertMappings error:', e);
    res.status(500).json({ error: 'DB error' });
  }
};