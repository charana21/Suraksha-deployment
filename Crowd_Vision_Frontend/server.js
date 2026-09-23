import 'dotenv/config'
import express from 'express'
import cors from 'cors'
import Twilio from 'twilio'
import fs from 'fs'
import os from 'os'
import path from 'path'
import { spawnSync } from 'child_process'
import { v4 as uuidv4 } from 'uuid'
import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3'

// ================= ENV VALIDATION =================
const requiredEnvVars = [
  'TWILIO_ACCOUNT_SID',
  'TWILIO_AUTH_TOKEN',
  'TWILIO_WHATSAPP_FROM',
  'AWS_ACCESS_KEY_ID',
  'AWS_SECRET_ACCESS_KEY',
  'AWS_REGION',
  'S3_BUCKET_NAME',
]

for (const key of requiredEnvVars) {
  if (!process.env[key]) {
    console.error(`❌ Missing env var: ${key}`)
    process.exit(1)
  }
}

// ================= EXPRESS =================
const app = express()
app.use(cors())
app.use(express.json())

// ================= TWILIO =================
const twilioClient = Twilio(
  process.env.TWILIO_ACCOUNT_SID,
  process.env.TWILIO_AUTH_TOKEN
)
const whatsappFrom = process.env.TWILIO_WHATSAPP_FROM

// ================= AWS S3 =================
const s3Client = new S3Client({
  region: process.env.AWS_REGION,
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
  },
})
const bucketName = process.env.S3_BUCKET_NAME

// ================= VOICE MAP =================
const voiceMap = {
  te: "te-IN-ShrutiNeural",
  hi: "hi-IN-SwaraNeural",
  en: "en-IN-NeerjaNeural",
}

// ================= HELPERS =================

function cleanupFile(filePath) {
  try {
    if (fs.existsSync(filePath)) fs.unlinkSync(filePath)
  } catch (e) {
    console.warn("Cleanup failed:", e.message)
  }
}

// Generate single language audio safely
function generateAudioFile(message, lang) {
  return new Promise((resolve, reject) => {
    const filename = path.join(os.tmpdir(), `${uuidv4()}-${lang}.mp3`)
    const voice = voiceMap[lang] || voiceMap.en

    console.log(`🎤 Generating ${lang} with voice ${voice}`)

    const result = spawnSync(
      "edge-tts",
      ["--voice", voice, "--text", message, "--write-media", filename],
      { encoding: "utf-8" }
    )

    if (result.error || result.status !== 0) {
      console.error(result.stderr)
      return reject(new Error("Edge TTS failed"))
    }

    resolve(filename)
  })
}

// Generate multi language audio
async function generateMultiLangAudio(message, lang) {
  const langMap = {
    te: ['te'],
    hi: ['hi'],
    en: ['en'],
    all: ['te', 'hi', 'en'],
  }

  const langs = langMap[lang] || ['en']
  const files = []

  for (const l of langs) {
    const f = await generateAudioFile(message, l)
    files.push(f)
  }

  if (files.length === 1) return files[0]

  const listFile = path.join(os.tmpdir(), `${uuidv4()}.txt`)
  const outFile = path.join(os.tmpdir(), `${uuidv4()}-merged.mp3`)

  fs.writeFileSync(
    listFile,
    files.map(f => `file '${f.replace(/\\/g, '/')}'`).join('\n')
  )

  const ffmpegResult = spawnSync("ffmpeg", [
    "-y",
    "-f", "concat",
    "-safe", "0",
    "-i", listFile,
    "-c", "copy",
    outFile
  ])

  files.forEach(f => cleanupFile(f))
  cleanupFile(listFile)

  if (ffmpegResult.status !== 0) {
    throw new Error("FFmpeg merge failed. Install ffmpeg properly.")
  }

  return outFile
}

// Upload to S3
async function uploadToS3(filePath) {
  const fileContent = fs.readFileSync(filePath)
  const key = `pa-audio/${uuidv4()}.mp3`

  await s3Client.send(new PutObjectCommand({
    Bucket: bucketName,
    Key: key,
    Body: fileContent,
    ContentType: "audio/mpeg",
  }))

  return `https://${bucketName}.s3.${process.env.AWS_REGION}.amazonaws.com/${key}`
}

// ================= ROUTES =================

app.get('/health', (req, res) => {
  res.json({ status: "ok", time: new Date().toISOString() })
})

app.post('/api/send-whatsapp-audio', async (req, res) => {
  const { phone, message, lang } = req.body

  if (!phone || !message) {
    return res.status(400).json({ error: "phone and message required" })
  }

  if (!/^\d{10}$/.test(phone)) {
    return res.status(400).json({ error: "Phone must be 10 digit Indian number" })
  }

  const validLangs = ['te', 'hi', 'en', 'all']
  const safeLang = validLangs.includes(lang) ? lang : 'en'

  let filePath = null
  let audioUrl = null

  try {
    filePath = await generateMultiLangAudio(message, safeLang)
    audioUrl = await uploadToS3(filePath)

    const langLabels = {
      te: "Telugu",
      hi: "Hindi",
      en: "English",
      all: "Telugu → Hindi → English"
    }

    const msg = await twilioClient.messages.create({
      from: whatsappFrom,
      to: `whatsapp:+91${phone}`,
      body: `📢 PA Announcement [${langLabels[safeLang]}]\n\n${message}`,
      mediaUrl: [audioUrl]
    })

    res.json({
      success: true,
      sid: msg.sid,
      audioUrl,
      lang: safeLang
    })

  } catch (err) {
    console.error("❌ Error:", err)
    res.status(500).json({ error: err.message })
  } finally {
    if (filePath) cleanupFile(filePath)
  }
})

// ================= SERVER =================
const PORT = process.env.PORT || 5000
const server = app.listen(PORT, () => {
  console.log(`✅ Server running on port ${PORT}`)
})

// ================= SHUTDOWN =================
process.on("SIGINT", () => shutdown("SIGINT"))
process.on("SIGTERM", () => shutdown("SIGTERM"))

function shutdown(signal) {
  console.log(`⚠️ ${signal} received. Shutting down...`)
  server.close(() => process.exit(0))
}