const express = require('express');
const ctrl = require('../controllers/serviceController');

const router = express.Router();
router.get('/status', ctrl.status);
// router.post('/start', ctrl.start);
// router.post('/stop', ctrl.stop);

module.exports = router;