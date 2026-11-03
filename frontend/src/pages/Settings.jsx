import { useState } from "react";
import "./Settings.css";

function Settings() {
  const [settings, setSettings] = useState({
    highRiskThreshold: 0.85,
    mediumRiskThreshold: 0.60,
    emailAlerts: true,
    smsAlerts: true,
    autoBlockHighRisk: false,
    notificationEmail: "fraud.team@bank.com",
    notificationPhone: "+234 801 234 5678",
  });

  const [saved, setSaved] = useState(false);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setSettings({
      ...settings,
      [name]: type === "checkbox" ? checked : value,
    });
    setSaved(false);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    // Later we will send this to the Django backend
    console.log("Settings saved:", settings);
    setSaved(true);

    // Hide success message after 3 seconds
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <div className="settings-page">
      <div className="settings-header">
        <div>
          <h1>Settings</h1>
          <p>Configure fraud detection thresholds and alert preferences</p>
        </div>
      </div>

      {saved && (
        <div className="success-message">
          Settings saved successfully!
        </div>
      )}

      <form onSubmit={handleSubmit} className="settings-form">
        {/* Risk Thresholds */}
        <div className="settings-card">
          <h2>Risk Thresholds</h2>
          <p className="card-description">
            Set the probability scores that determine High and Medium risk levels.
          </p>

          <div className="form-row">
            <div className="form-group">
              <label>High Risk Threshold</label>
              <div className="input-with-suffix">
                <input
                  type="number"
                  name="highRiskThreshold"
                  min="0"
                  max="1"
                  step="0.01"
                  value={settings.highRiskThreshold}
                  onChange={handleChange}
                />
                <span className="suffix">(0 - 1)</span>
              </div>
              <small>Transactions above this score will be marked as High Risk</small>
            </div>

            <div className="form-group">
              <label>Medium Risk Threshold</label>
              <div className="input-with-suffix">
                <input
                  type="number"
                  name="mediumRiskThreshold"
                  min="0"
                  max="1"
                  step="0.01"
                  value={settings.mediumRiskThreshold}
                  onChange={handleChange}
                />
                <span className="suffix">(0 - 1)</span>
              </div>
              <small>Transactions above this score will be marked as Medium Risk</small>
            </div>
          </div>
        </div>

        {/* Alert Channels */}
        <div className="settings-card">
          <h2>Alert Channels</h2>
          <p className="card-description">
            Choose how fraud alerts should be delivered.
          </p>

          <div className="toggle-group">
            <label className="toggle-item">
              <div>
                <span className="toggle-title">Email Alerts</span>
                <span className="toggle-desc">Send alerts via email</span>
              </div>
              <input
                type="checkbox"
                name="emailAlerts"
                checked={settings.emailAlerts}
                onChange={handleChange}
              />
            </label>

            <label className="toggle-item">
              <div>
                <span className="toggle-title">SMS Alerts</span>
                <span className="toggle-desc">Send alerts via SMS</span>
              </div>
              <input
                type="checkbox"
                name="smsAlerts"
                checked={settings.smsAlerts}
                onChange={handleChange}
              />
            </label>

            <label className="toggle-item">
              <div>
                <span className="toggle-title">Auto-block High Risk</span>
                <span className="toggle-desc">
                  Automatically block transactions with very high risk scores
                </span>
              </div>
              <input
                type="checkbox"
                name="autoBlockHighRisk"
                checked={settings.autoBlockHighRisk}
                onChange={handleChange}
              />
            </label>
          </div>
        </div>

        {/* Notification Contacts */}
        <div className="settings-card">
          <h2>Notification Contacts</h2>
          <p className="card-description">
            Default email and phone number that will receive fraud alerts.
          </p>

          <div className="form-row">
            <div className="form-group">
              <label>Notification Email</label>
              <input
                type="email"
                name="notificationEmail"
                value={settings.notificationEmail}
                onChange={handleChange}
              />
            </div>

            <div className="form-group">
              <label>Notification Phone</label>
              <input
                type="text"
                name="notificationPhone"
                value={settings.notificationPhone}
                onChange={handleChange}
              />
            </div>
          </div>
        </div>

        {/* Save Button */}
        <div className="form-actions">
          <button type="submit" className="save-btn">
            Save Settings
          </button>
        </div>
      </form>
    </div>
  );
}

export default Settings;