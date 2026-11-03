import { useState } from "react";
import { Link } from "react-router-dom";
import "./Alerts.css";

function Alerts() {
  // Temporary fake data (we will replace with real API later)
  const [alerts] = useState([
    {
      id: "ALT-001",
      transactionId: "TXN001",
      account: "2345****8912",
      amount: 45000,
      risk: "high",
      channel: "Email + SMS",
      status: "sent",
      time: "2 mins ago",
      message: "High risk transaction detected. Amount significantly higher than usual.",
    },
    {
      id: "ALT-002",
      transactionId: "TXN004",
      account: "3456****7890",
      amount: 97500,
      risk: "high",
      channel: "Email + SMS",
      status: "sent",
      time: "12 mins ago",
      message: "Suspicious transfer to a new beneficiary.",
    },
    {
      id: "ALT-003",
      transactionId: "TXN002",
      account: "5678****2341",
      amount: 8500,
      risk: "medium",
      channel: "Email",
      status: "pending",
      time: "18 mins ago",
      message: "Multiple transactions in a short period.",
    },
    {
      id: "ALT-004",
      transactionId: "TXN008",
      account: "1122****3344",
      amount: 156000,
      risk: "high",
      channel: "Email + SMS",
      status: "failed",
      time: "25 mins ago",
      message: "Possible account takeover attempt.",
    },
    {
      id: "ALT-005",
      transactionId: "TXN011",
      account: "7788****9900",
      amount: 3200,
      risk: "low",
      channel: "Email",
      status: "sent",
      time: "40 mins ago",
      message: "Unusual location detected.",
    },
  ]);

  const getRiskClass = (risk) => {
    if (risk === "high") return "risk-high";
    if (risk === "medium") return "risk-medium";
    return "risk-low";
  };

  const getStatusClass = (status) => {
    if (status === "sent") return "status-sent";
    if (status === "pending") return "status-pending";
    return "status-failed";
  };

  return (
    <div className="alerts-page">
      {/* Header */}
      <div className="alerts-header">
        <div>
          <h1>Alerts</h1>
          <p>Real-time fraud alerts and notifications</p>
        </div>
        <button className="refresh-btn">Refresh</button>
      </div>

      {/* Summary Cards */}
      <div className="alerts-summary">
        <div className="summary-card">
          <span className="label">Total Alerts</span>
          <span className="value">5</span>
        </div>
        <div className="summary-card">
          <span className="label">High Risk</span>
          <span className="value red">3</span>
        </div>
        <div className="summary-card">
          <span className="label">Pending</span>
          <span className="value orange">1</span>
        </div>
        <div className="summary-card">
          <span className="label">Failed</span>
          <span className="value gray">1</span>
        </div>
      </div>

      {/* Alerts Table */}
      <div className="alerts-table-container">
        <table>
          <thead>
            <tr>
              <th>Alert ID</th>
              <th>Transaction</th>
              <th>Account</th>
              <th>Amount</th>
              <th>Risk</th>
              <th>Channel</th>
              <th>Status</th>
              <th>Time</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((alert) => (
              <tr key={alert.id}>
                <td className="alert-id">{alert.id}</td>
                <td>{alert.transactionId}</td>
                <td>{alert.account}</td>
                <td>₦{alert.amount.toLocaleString()}</td>
                <td>
                  <span className={`risk-badge ${getRiskClass(alert.risk)}`}>
                    {alert.risk.toUpperCase()}
                  </span>
                </td>
                <td>{alert.channel}</td>
                <td>
                  <span className={`status-badge ${getStatusClass(alert.status)}`}>
                    {alert.status.toUpperCase()}
                  </span>
                </td>
                <td>{alert.time}</td>
                <td>
                  <Link to={`/alerts/${alert.id}`} className="view-btn">
                    View
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default Alerts;