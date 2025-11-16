require('dotenv').config();

const config = {
  port: process.env.PORT || 4000,
  db: {
    host: process.env.DB_HOST || 'localhost',
    user: process.env.DB_USER || 'bluetooth_app',
    password: process.env.DB_PASSWORD || 'Strong_Password_ChangeMe!',
    database: process.env.DB_NAME || 'bluetooth_sensor_db',
    connectionLimit: parseInt(process.env.DB_POOL || '10', 10),
  },
  pyServiceName: process.env.PY_SERVICE_NAME || 'SylvacReader',
};

module.exports = config;