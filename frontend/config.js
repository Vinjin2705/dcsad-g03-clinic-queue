/**
 * University of Makati — ELEC3 Cloud Computing (Track B Final Exam)
 * Section IV-DCSAD | Group 3 (dcsad-g03)
 * Case 4: School Clinic Visit Queue
 *
 * Frontend Configuration File
 * When testing locally, default to http://localhost:8000
 * When deploying to S3 (umak-elec3-dcsad-g03-clinic-web), swap API_BASE_URL to:
 * https://<api-id>.execute-api.ap-southeast-1.amazonaws.com
 */

const CONFIG = {
  // Local development default:
  API_BASE_URL: "https://x9mmdpwelc.execute-api.ap-southeast-1.amazonaws.com
",

  // Class AWS Lab Account deployment endpoint placeholder:
  // API_BASE_URL: "https://your-api-id.execute-api.ap-southeast-1.amazonaws.com",

  // Polling interval in milliseconds for live status updates
  POLL_INTERVAL_MS: 4000,
};
