/**
 * Downtime Monitoring Script (Node.js Version)
 * ============================================
 * This script checks the MongoDB 'analytics' collection to ensure the CrowdVision system
 * is actively pushing data. If no new data has been received for > 1 hour, it sends
 * an email alert.
 *
 * DEPLOYMENT INSTRUCTIONS:
 * -----------------------
 * 1. Run this script on an EXTERNAL server (not the local machine running CrowdVision).
 * 2. Install dependencies:
 *    npm install mongodb nodemailer
 * 3. Set the Environment Variables below (or create a .env file and use dotenv).
 * 4. Schedule via Cron (Linux) or Task Scheduler (Windows).
 *    Example: *\/20 * * * * node /path/to/monitor_downtime.js >> /var/log/downtime.log 2>&1
 */

const { MongoClient } = require('mongodb');
const nodemailer = require('nodemailer');
const fs = require('fs');
const path = require('path');
const { Client: TwilioClient } = require('twilio');

// =============================================================================
// CONFIGURATION
// =============================================================================

// --- Database Configuration ---
// URI to the PRODUCTION/CLOUD MongoDB
// const MONGODB_URI = "mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority";
const MONGODB_URI = process.env.MONGODB_URI;

// --- Alert Threshold ---
const ALERT_THRESHOLD_MINUTES = 60;

// --- Email Configuration ---
const SMTP_SERVER = process.env.SMTP_SERVER || "smtp.gmail.com";
const SMTP_PORT = Number.parseInt(process.env.SMTP_PORT || "587", 10);
const SMTP_USERNAME = process.env.SMTP_USERNAME;
const SMTP_PASSWORD = process.env.SMTP_PASSWORD;
const ALERT_RECEIVER_EMAILS = process.env.ALERT_RECEIVER_EMAILS || "";

// --- WhatsApp Configuration ---
const TWILIO_ACCOUNT_SID = process.env.TWILIO_ACCOUNT_SID;
const TWILIO_AUTH_TOKEN = process.env.TWILIO_AUTH_TOKEN;
const TWILIO_WHATSAPP_NUMBER = process.env.TWILIO_WHATSAPP_NUMBER; // e.g., 'whatsapp:+14155238886'
const ALERT_RECEIVER_WHATSAPP = process.env.ALERT_RECEIVER_WHATSAPP || "";
const twilioClient = TWILIO_ACCOUNT_SID && TWILIO_AUTH_TOKEN ? new TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) : null;

// =============================================================================
// LOGIC
// =============================================================================

async function sendAlertEmail(lastSeenTime, minutesAgo) {
    if (!SMTP_USERNAME || !SMTP_PASSWORD || !ALERT_RECEIVER_EMAILS) {
        console.error("ERROR: Email credentials not configured. Skipping alert.");
        return;
    }

    const receivers = ALERT_RECEIVER_EMAILS.split(',').map(e => e.trim()).filter(e => e);
    if (receivers.length === 0) {
        console.error("ERROR: No receiver emails configured.");
        return;
    }

    const subject = `🔴 ALERT: CrowdVision System Downtime Detected (${minutesAgo.toFixed(0)} mins)`;
    
    const body = `
    <html>
      <body>
        <h2 style="color: #D32F2F;">System Downtime Alert</h2>
        <p>The CrowdVision system appears to be offline or unreachable.</p>
        
        <ul>
          <li><strong>Last Active:</strong> ${lastSeenTime.toUTCString()}</li>
          <li><strong>Downtime Duration:</strong> ${minutesAgo.toFixed(1)} minutes</li>
          <li><strong>Threshold:</strong> ${ALERT_THRESHOLD_MINUTES} minutes</li>
        </ul>
        
        <p>Possible causes:</p>
        <ul>
          <li>Power failure at the deployment site.</li>
          <li>Internet connectivity loss.</li>
          <li>Application crash (check systemd status).</li>
        </ul>
        
        <p><em>This is an automated message from the external monitoring script.</em></p>
      </body>
    </html>
    `;

    const transporter = nodemailer.createTransport({
        host: SMTP_SERVER,
        port: SMTP_PORT,
        secure: false, // true for 465, false for other ports
        auth: {
            user: SMTP_USERNAME,
            pass: SMTP_PASSWORD,
        },
    });

    try {
        await transporter.sendMail({
            from: SMTP_USERNAME,
            to: receivers.join(', '),
            subject: subject,
            html: body,
        });
        console.log(`✅ Alert email sent to ${receivers.length} recipients.`);
    } catch (error) {
        console.error(`❌ Failed to send email: ${error.message}`);
    }
}

async function sendAlertWhatsApp(lastSeenTime, minutesAgo) {
    if (!twilioClient || !TWILIO_WHATSAPP_NUMBER || !ALERT_RECEIVER_WHATSAPP) {
        console.error("ERROR: WhatsApp credentials not configured. Skipping WhatsApp alert.");
        return;
    }

    const receivers = ALERT_RECEIVER_WHATSAPP.split(',').map(e => e.trim()).filter(e => e);
    if (receivers.length === 0) {
        console.error("ERROR: No WhatsApp receiver numbers configured.");
        return;
    }

    const message =
        `🚨 System Downtime Alert 🚨\n` +
        `Last Active: ${lastSeenTime.toUTCString()}\n` +
        `Downtime Duration: ${minutesAgo.toFixed(1)} minutes\n` +
        `Threshold: ${ALERT_THRESHOLD_MINUTES} minutes\n` +
        `Possible causes: Power failure, Internet loss, Application crash.\n` +
        `This is an automated message from the external monitoring script.`;

    for (const number of receivers) {
        try {
            const msg = await twilioClient.messages.create({
                body: message,
                from: TWILIO_WHATSAPP_NUMBER,
                to: `whatsapp:${number}`
            });
            console.log(`✅ WhatsApp alert sent to ${number}: ${msg.sid}`);
        } catch (error) {
            console.error(`❌ Failed to send WhatsApp alert to ${number}: ${error.message}`);
        }
    }
}

async function main() {
    if (!MONGODB_URI) {
        console.error("❌ Error: MONGODB_URI not set.");
        console.error("Please set the environment variable or edit the script configuration.");
        process.exit(1);
    }

    console.log("Connecting to MongoDB...");
    const client = new MongoClient(MONGODB_URI, { serverSelectionTimeoutMS: 10000 });

    try {
        await client.connect();
        const db = client.db("crowdvision"); // Assuming DB name is 'crowdvision'
        const collection = db.collection("analytics");

        // Get the very last timestamp recorded
        const lastRecord = await collection.findOne({}, { sort: { timestamp: -1 } });

        if (!lastRecord) {
            console.warn("⚠️ No data found in 'analytics' collection.");
            return;
        }

        const lastTimestamp = new Date(lastRecord.timestamp);
        const currentTime = new Date();
        
        // Calculate difference in minutes
        const diffMs = currentTime - lastTimestamp;
        const minutesAgo = diffMs / (1000 * 60);

        console.log(`Last heartbeat: ${lastTimestamp.toISOString()} (${minutesAgo.toFixed(2)} minutes ago)`);

        const alertMarkerFile = path.resolve(__dirname, "downtime_alert_sent.txt");

        if (minutesAgo > ALERT_THRESHOLD_MINUTES) {
            console.error(`❌ ALERT: System inactive for > ${ALERT_THRESHOLD_MINUTES} minutes!`);
            
            // Check marker file to prevent spam
            let shouldSend = true;
            if (fs.existsSync(alertMarkerFile)) {
                const stats = fs.statSync(alertMarkerFile);
                const fileAgeMs = new Date() - stats.mtime;
                const hoursSinceAlert = fileAgeMs / (1000 * 60 * 60);
                
                if (hoursSinceAlert < 24) { // One alert per 24 hours
                    console.log("Skipping email: Alert already sent in last 24h.");
                    shouldSend = false;
                }
            }
            
            if (shouldSend) {
                await sendAlertEmail(lastTimestamp, minutesAgo);
                await sendAlertWhatsApp(lastTimestamp, minutesAgo);
                // Create/Update marker file
                fs.writeFileSync(alertMarkerFile, new Date().toISOString());
            }

        } else {
            console.log("✅ System status: ONLINE");
            // If system is back online, remove marker file so we can alert again next time
            if (fs.existsSync(alertMarkerFile)) {
                fs.unlinkSync(alertMarkerFile);
                console.log("System recovered. Alert marker cleared.");
            }
        }

    } catch (error) {
        console.error(`❌ Error Checking Status: ${error.message}`);
    } finally {
        await client.close();
    }
}

main().catch(console.error);
