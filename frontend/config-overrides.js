const path = require("path");

module.exports = function override(config) {
    // Add @ alias pointing to src/
    config.resolve = config.resolve || {};
    config.resolve.alias = config.resolve.alias || {};
    config.resolve.alias["@"] = path.resolve(__dirname, "src");
    return config;
};
