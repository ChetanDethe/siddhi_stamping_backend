const express = require('express');
const cors = require('cors');
const config = require('./config/env');

const mappings = require('./routes/mappings');
const readings = require('./routes/readings');
const service = require('./routes/service');

const app = express();
app.use(cors());
app.use(express.json());

// Routes
app.use('/api/mappings', mappings);
app.use('/api/readings', readings);
app.use('/api/script', service);


// Health
app.get('/api/health', (req, res) => res.json({ ok: true, ts: Date.now() }));

app.listen(config.port, () => {
  console.log(`API listening on http://localhost:${config.port}`);
});