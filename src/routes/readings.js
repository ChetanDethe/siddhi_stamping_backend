const express = require('express');
const ctrl = require('../controllers/readingsController');

const router = express.Router();
router.get('/latest', ctrl.getLatest);

module.exports = router;