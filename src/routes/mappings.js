const express = require('express');
const ctrl = require('../controllers/mappingController');

const router = express.Router();
router.get('/', ctrl.getMappings);
router.post('/', ctrl.upsertMappings);

module.exports = router;