import { useState } from "react";
import "./Dashboard.css";

function Dashboard() {
  // Temporary fake data (we will replace this with real API data later)
  const [transactions] = useState([
    {
      id: "TXN001",
      account: "2345****8912",
      amount: 45000,
      channel: "Mobile",
      time: "2 mins ago",
      risk: "high",
      status: "Fraud Detected",
    },
    {
      id: "TXN002",
      account: "5678****2341",
      amount: 8500,
      channel: "Internet Banking",
      time: "5 mins ago",
      risk: "medium",
      status: "Under Review",
    },
    {
      id: "TXN003",
      account: "9012****4567",
      amount: 1200,
      channel: "USSD",
      time: "8 mins ago",
      risk: "low",
      status: "Legitimate",
    },
    {
      id: "TXN004",
      account: "3456****7890",
      amount: 97500,
      channel: "Mobile",
      time: "12 mins ago",
      risk: "high",
      status: "Fraud Detected",
    },
    {
      id: "TXN005",
      account: "7890****1234",
      amount: 3200,
      channel: "POS",
      time: "15 mins ago",
      risk: "low",
      status: "Legitimate",
    },
  ]);

  // Helper function to get colour class based on risk
  const getRiskClass = (risk) => {
    if (risk === "high") return "risk-high";
    if (risk === "medium") return "risk-medium";
    return "risk-low";
  };

  return (
    <div className="dashboard">
      {/* Page Title */}
      <div className="dashboard-header">
        <h1>Fraud Detection Dashboard</h1>
        <p>Real-time monitoring of digital banking transactions</p>
      </div>

      {/* Summary Cards */}
      <div className="summary-cards">
        <div className="card">
          <h3>Total Transactions</h3>
          <p className="number">1,248</p>
          <span className="label">Today</span>
        </div>

        <div className="card">
          <h3>Fraud Detected</h3>
          <p className="number red">23</p>
          <span className="label">Today</span>
        </div>

        <div className="card">
          <h3>High Risk</h3>
          <p className="number orange">41</p>
          <span className="label">Pending Review</span>
        </div>

        <div className="card">
          <h3>Avg. Response Time</h3>
          <p className="number">4.7s</p>
          <span className="label">Last 24 hours</span>
        </div>
      </div>

      {/* Recent Transactions Table */}
      <div className="transactions-section">
        <div className="section-header">
          <h2>Recent Transactions</h2>
          <button className="refresh-btn">Refresh</button>
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Transaction ID</th>
                <th>Account</th>
                <th>Amount (₦)</th>
                <th>Channel</th>
                <th>Time</th>
                <th>Risk Level</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((txn) => (
                <tr key={txn.id}>
                  <td>{txn.id}</td>
                  <td>{txn.account}</td>
                  <td>₦{txn.amount.toLocaleString()}</td>
                  <td>{txn.channel}</td>
                  <td>{txn.time}</td>
                  <td>
                    <span className={`risk-badge ${getRiskClass(txn.risk)}`}>
                      {txn.risk.toUpperCase()}
                    </span>
                  </td>
                  <td>{txn.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;