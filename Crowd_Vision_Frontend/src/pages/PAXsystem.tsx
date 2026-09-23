import React, { useState, FocusEvent } from 'react'
import { PageLayout } from '@/components/layout/PageLayout'
import './PAXsystem.css'

// valid identifiers for zone and language selections

type ZoneId = 'all' | 'platforms' | 'fob' | 'booking'
type LangId = 'te' | 'hi' | 'en' | 'all'

const ZONES: {id: ZoneId; label: string}[] = [
  {id:'all',      label:'🔊 All Zones (Station-wide)'},
  {id:'platforms',label:'🚉 Platforms Only'},
  {id:'fob',      label:'🌉 FOBs & Concourse'},
  {id:'booking',  label:'🎫 Booking Office Area'},
]
const LANGS: {id: LangId; label: string}[] = [
  {id:'te',  label:'Telugu'},
  {id:'hi',  label:'Hindi'},
  {id:'en',  label:'English'},
  {id:'all', label:'🌐 All Languages'},
]
type SpokenLang = 'te' | 'hi' | 'en'
interface QuickItem {
  label: string
  // messages in each supported spoken language
  te: string
  hi: string
  en: string
}

const QUICK: QuickItem[] = [
  {
    label:'Track safety',
    te:'ప్రయాణికులు సురక్షితంగా ఫుట్ ఓవర్ బ్రిడ్జ్ ఉపయోగించండి. ట్రాక్ దాటవద్దు.',
    hi:'यात्रियों से अनुरोध है कि सुरक्षित पार करने के लिए FOB का उपयोग करें। ट्रैक पार न करें।',
    en:'Passengers are requested to use the FOB for safe crossing. Do not cross the tracks.'
  },
  {
    label:'Crowd dispersal',
    te:'ప్లాట్‌ఫారం 1లో భారీ రద్దీ ఉంది. ప్రయాణికులు దయచేసి ప్లాట్‌ఫారం 4 మరియు 5కి వెళ్లండి.',
    hi:'प्लेटफॉर्म 1 पर भारी भीड़ है। कृपया प्लेटफॉर्म 4 और 5 पर जाएं।',
    en:'Attention passengers: Heavy crowd on Platform 1. Please move to Platform 4–5 for boarding.'
  },
  {
    label:'RPF deployment',
    te:'ఆర్‌పిఎఫ్ సిబ్బంది వెంటనే ప్లాట్‌ఫారం 1 ట్రాక్ జోన్‌కు చేరుకోవాలి.',
    hi:'आरपीएफ कर्मी तुरंत प्लेटफॉर्म 1 ट्रैक ज़ोन पर रिपोर्ट करें।',
    en:'RPF personnel report immediately to Track Zone — Platform 1.'
  },
  {
    label:'Train delay',
    te:'హైదరాబాద్-కరీంనగర్ ఎక్స్‌ప్రెస్ ప్లాట్‌ఫారం 2లో 45 నిమిషాలు ఆలస్యం అయింది.',
    hi:'हैदराबाद-करिमनगर एक्सप्रेस प्लेटफॉर्म 2 पर 45 मिनट की देरी से आएगी।',
    en:'The Hyderabad-Karimnagar Express on Platform 2 is delayed by 45 minutes. We apologise for the inconvenience.'
  },
  {
    label:'Platform change',
    te:'12723 తెలంగాణ ఎక్స్‌ప్రెస్ ప్లాట్‌ఫారం నంబర్ 6 నుండి 5కి మార్చబడింది.',
    hi:'12723 तेलंगाना एक्सप्रेस का प्लेटफॉर्म नंबर 6 से बदलकर 5 कर दिया गया है।',
    en:'May I have your attention please? The platform number of 12723 Telangana Express has been changed from Platform 6 to Platform 5.'
  },
  {
    label:'Emergency',
    te:'ప్లాట్‌ఫారం 3లో అత్యవసర పరిస్థితి. వెంటనే ప్రధాన గేటు వైపు వెళ్లండి.',
    hi:'प्लेटफॉर्म 3 पर आपात स्थिति। तुरंत मुख्य निकास की ओर जाएं।',
    en:'Attention: Emergency evacuation on Platform 3. Move towards the main exit immediately.'
  },
]
const INIT_LOG = [
  {msg:'Passengers please maintain safe distance on Platform 2 and use designated waiting areas.',ch:'🔊 Speakers + 💬 WhatsApp',lang:'Hindi',  time:'11:42 AM'},
  {msg:'RPF personnel report to Gate 3 immediately for crowd control assistance.',               ch:'🔊 Speakers',               lang:'Telugu', time:'11:18 AM'},
]

// browser speech — uses full locale codes
function speak(text: string, langId: string): void {
  if (!window.speechSynthesis) return
  window.speechSynthesis.cancel()
  const localeMap: Record<string, string> = { te:'te-IN', hi:'hi-IN', en:'en-IN' }
  const langs = langId === 'all'
    ? ['te-IN', 'hi-IN', 'en-IN']
    : [localeMap[langId] || langId]
  let delay = 0
  langs.forEach(lang => {
    window.setTimeout(() => {
      const u = new SpeechSynthesisUtterance(text)
      u.lang = lang; u.rate = 0.9; u.volume = 1
      window.speechSynthesis.speak(u)
    }, delay)
    delay += 4000
  })
}

interface LogEntry {
  msg: string
  ch: string
  lang: string
  time: string
  fresh?: boolean
}

export default function PASystem() {
  const RAW_API_BASE_URL = (import.meta.env.VITE_API_URL as string) || ""
  const API_BASE_URL = RAW_API_BASE_URL.replace(/\/+$/, '')
  const API_ROOT = API_BASE_URL.endsWith('/api') ? API_BASE_URL : `${API_BASE_URL}/api`
  const [zone,     setZone]     = useState<ZoneId>('all')
  const [lang,     setLang]     = useState<LangId>('te')   // gtts codes: te, hi, en, all
  const [msg,      setMsg]      = useState<string>('')
  const [phone,    setPhone]    = useState<string>('')
  const [speakers, setSpeakers] = useState<boolean>(true)
  const [whatsapp, setWhatsapp] = useState<boolean>(true)
  const [sms,      setSms]      = useState<boolean>(false)
  const [voice,    setVoice]    = useState<boolean>(true)
  const [sending,  setSending]  = useState<boolean>(false)
  const [sent,     setSent]     = useState<boolean>(false)
  const [log,      setLog]      = useState<LogEntry[]>(INIT_LOG)
  const [toast,    setToast]    = useState<string | null>(null)
  const [playing,  setPlaying]  = useState<boolean>(false)

  async function syncWhatsAppOptIn(enabled: boolean) {
    if (phone.length !== 10) {
      if (enabled) {
        setToast('❌ Enter a valid 10-digit phone number before enabling WhatsApp alerts')
        setTimeout(() => setToast(null), 3000)
      }
      return
    }

    try {
      const token = localStorage.getItem('auth_token')
      const res = await fetch(`${API_ROOT}/trains/whatsapp/opt-in`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          phone_number: `+91${phone}`,
          full_name: 'Passenger',
          enabled,
        }),
      })

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data?.detail || data?.message || 'Failed to save WhatsApp preference')
      }

      if (enabled) {
        setToast('✅ WhatsApp preference saved. Opt-in request sent; user must reply YES to confirm.')
      } else {
        setToast('✅ WhatsApp alerts disabled')
      }
      setTimeout(() => setToast(null), 4000)
    } catch (err: any) {
      setToast(`❌ ${err?.message || 'Failed to update WhatsApp preference'}`)
      setTimeout(() => setToast(null), 4000)
    }
  }

  async function sendWhatsApp() {
    if (phone.length !== 10 || !msg.trim()) return
    try {
      const token = localStorage.getItem('auth_token')
      const res = await fetch(`${API_ROOT}/trains/whatsapp/send-text`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          phone_number: `+91${phone}`,
          message: msg,
        }),
      })

      let data
      const text = await res.text()
      try {
        data = text ? JSON.parse(text) : {}
      } catch {
        data = { success: res.ok, message: text }
      }

      if (res.ok && data.status === 'success') {
        setToast('💬 WhatsApp text message sent successfully!')
        setTimeout(() => setToast(null), 4000)
      } else {
        throw new Error(data.detail || data.error || data.message || 'Failed')
      }
    } catch (err) {
      setToast('❌ Failed to send WhatsApp text: ' + err.message)
      setTimeout(() => setToast(null), 5000)
    }
  }

  function broadcast() {
    if (!msg.trim()) return
    if (whatsapp && phone.length !== 10) {
      setToast('❌ Enter a valid 10-digit phone number for WhatsApp')
      setTimeout(() => setToast(null), 3000)
      return
    }

    setSending(true)

    if (whatsapp) {
      sendWhatsApp()
    }

    if (voice && speakers) {
      speak(msg, lang)
      setPlaying(true)
      setTimeout(() => setPlaying(false), (lang === 'all' ? 3 : 1) * 4200)
    }

    setTimeout(() => {
      setSending(false); setSent(true)
      const ch = [
        speakers && '🔊 Speakers',
        whatsapp  && (`💬 WhatsApp${voice ? ' (audio)' : ''}`),
        sms       && '📱 SMS',
        voice     && '🔈 Voice',
      ].filter(Boolean).join(' + ')
      const now = new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})
      const lLabel = LANGS.find(l => l.id === lang)?.label || lang
      setLog(p => [{msg, ch, lang: lLabel, time: now, fresh: true}, ...p])
      setToast('📢 Announcement broadcast successfully!')
      setTimeout(() => { setToast(null); setSent(false); setMsg('') }, 4000)
    }, voice ? 2000 : 1200)
  }

  const inp = {
    width:'100%', background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.1)',
    borderRadius:8, padding:'10px 12px', fontSize:13, color:'#e2e8f0',
    fontFamily:'Outfit,sans-serif', outline:'none', transition:'border-color 0.2s',
  }
  const focusIn  = (e: FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    e.currentTarget.style.borderColor = 'rgba(37,99,235,0.6)'
  }
  const focusOut = (e: FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)'
  }

  return (
    <PageLayout>
      <div className="pa-body animate-fade-in">

      <div className="pa-title-section">
        <h1 className="pa-title">
          📢 PA System
        </h1>
        <p className="pa-subtitle">Public Address — Voice & Text Announcement Broadcasting</p>
      </div>

      {/* Status */}
      <div className="glass pa-status-banner">
        <div style={{display:'flex', alignItems:'center', gap:8}}>
          <div style={{width:8, height:8, borderRadius:'50%', background:'#22c55e', boxShadow:'0 0 6px #22c55e'}} className="live-dot"/>
          <span style={{fontWeight:600, fontSize:13, color:'#86efac'}}>All Speakers Online — 24 zones active</span>
        </div>
        <div style={{display:'flex', gap:12, fontSize:12, color:'#9fb2c8'}}>
          <span>💬 WhatsApp: ✅ Connected</span>
          <span>🔈 Voice TTS: ✅ Ready</span>
        </div>
      </div>

      {/* Zone */}
      <div className="glass" style={{padding:20}}>
        <div className="pa-section-label">📡 Broadcast Zone</div>
        <div className="pa-zone-grid">
          {ZONES.map(z => (
            <button key={z.id} onClick={() => setZone(z.id)} className="pa-btn" style={{
              background: zone===z.id ? 'rgba(37,99,235,0.2)' : 'rgba(255,255,255,0.03)',
              border: '1px solid ' + (zone===z.id ? 'rgba(37,99,235,0.5)' : 'rgba(255,255,255,0.08)'),
              color: zone===z.id ? '#bfdbfe' : '#b8c7d9',
            }}>{z.label}</button>
          ))}
        </div>
      </div>

      {/* Language */}
      <div className="glass" style={{padding:20}}>
        <div className="pa-section-label">🌐 Announcement Language</div>
        <div className="pa-lang-flex">
          {LANGS.map(l => (
            <button key={l.id} onClick={() => setLang(l.id)} className="pa-lang-btn" style={{
              background: lang===l.id ? 'rgba(37,99,235,0.2)' : 'rgba(255,255,255,0.03)',
              border: '1px solid ' + (lang===l.id ? 'rgba(37,99,235,0.5)' : 'rgba(255,255,255,0.08)'),
              color: lang===l.id ? '#bfdbfe' : '#b8c7d9',
            }}>{l.label}</button>
          ))}
        </div>
        {lang === 'all' && (
          <div style={{marginTop:10, fontSize:11, color:'#facc15'}}>
            🌐 All Languages selected — audio will be sent in Telugu → Hindi → English sequence
          </div>
        )}
      </div>

      {/* Message */}
      <div className="glass" style={{padding:20}}>
        <div className="pa-section-label">✍️ Announcement Message</div>
        <div className="pa-quick-flex">
          {QUICK.map(q => (
            <button key={q.label} onClick={() => {
              // lang may be 'all' so fall back to English
              const text = lang === 'all'
                ? q.en
                : q[lang as SpokenLang] || q.en
              setMsg(text)
            }}
              className="pa-quick-btn"
            >{q.label}</button>
          ))}
        </div>
        <textarea value={msg} onChange={e => setMsg(e.target.value)} maxLength={500}
          placeholder="Type your announcement message here..." rows={4}
          className="pa-textarea" onFocus={focusIn} onBlur={focusOut}/>
        <div style={{textAlign:'right', marginTop:4, fontSize:11, color:'#7f93ad'}}>{msg.length} / 500</div>
      </div>

      {/* Phone */}
      <div className="glass" style={{padding:20}}>
        <div className="pa-section-label">📱 Recipient Phone Number</div>
        <div className="pa-phone-row">
          <div className="pa-phone-input-wrap">
            <div className="pa-phone-prefix">
              🇮🇳 <span style={{fontSize:12, color:'#9fb2c8'}}>+91</span>
            </div>
            <input type="tel" value={phone} placeholder="Enter 10-digit mobile number"
              onChange={e => setPhone(e.target.value.replace(/[^0-9]/g,'').slice(0,10))}
              className="pa-textarea" style={{paddingLeft:70}} onFocus={focusIn} onBlur={focusOut}/>
          </div>
          {/* <button onClick={() => {
            if (phone.length === 10) {
              speak('Test announcement. PA System active.', lang)
              setToast('🔈 Test voice played')
              setTimeout(() => setToast(null), 3000)
            }
          }} style={{background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.1)',
            borderRadius:8, padding:'10px 16px', color:'#94a3b8', fontSize:12, fontWeight:600,
            cursor:'pointer', fontFamily:'Outfit,sans-serif', whiteSpace:'nowrap'}}>
            🔈 Test Voice
          </button> */}
        </div>
        {phone.length > 0 && phone.length < 10 && (
          <div style={{fontSize:11, color:'#ef4444', marginTop:6}}>Please enter a valid 10-digit number</div>
        )}
        {phone.length === 10 && (
          <div style={{fontSize:11, color:'#86efac', marginTop:6}}>
            ✅ +91 {phone} — Ready for WhatsApp / SMS
          </div>
        )}
      </div>

      {/* Send via + button */}
      <div className="glass" style={{padding:20}}>
        <div className="pa-section-label">📤 Send Via</div>
        <div style={{display:'flex', gap:20, marginBottom:18, flexWrap:'wrap'}}>
          {[
            {id:'speakers', label:'🔊 Station Speakers',        val:speakers, set:setSpeakers},
            {id:'whatsapp', label:'💬 WhatsApp (Staff Group)',   val:whatsapp, set:setWhatsapp},
            {id:'sms',      label:'📱 SMS Alert',                val:sms,      set:setSms},
            {id:'voice',    label:'🔈 Voice Announcement (TTS)', val:voice,    set:setVoice},
          ].map(item => (
            <label key={item.label} style={{display:'flex', alignItems:'center', gap:7, color:'#cbd5e1', fontSize:13, cursor:'pointer'}}>
              <input
                type="checkbox"
                checked={item.val}
                onChange={async (e) => {
                  const checked = e.target.checked
                  item.set(checked)
                  if (item.id === 'whatsapp') {
                    await syncWhatsAppOptIn(checked)
                  }
                }}
                style={{width:15, height:15, accentColor:'#2563eb'}}/>
              {item.label}
            </label>
          ))}
        </div>

        {voice && (
          <div style={{background:'rgba(37,99,235,0.1)', border:'1px solid rgba(37,99,235,0.25)',
            borderRadius:8, padding:'10px 14px', marginBottom:16, fontSize:12, color:'#93c5fd'}}>
            🔈 Voice TTS: Message will be spoken in <strong>{LANGS.find(l => l.id === lang)?.label}</strong>.
            {lang === 'all' && <span style={{color:'#facc15'}}> (Telugu → Hindi → English)</span>}
            {playing && <span style={{color:'#86efac', fontWeight:700, marginLeft:8}}>▶ Playing now...</span>}
          </div>
        )}

        {whatsapp && (
          <div style={{fontSize:12, color:'#93c5fd', marginBottom:16}}>
            WhatsApp sends plain text alerts from backend (opt-in confirmation required).
          </div>
        )}

        <button onClick={broadcast} disabled={sending || !msg.trim() || (whatsapp && phone.length !== 10)} 
          className="pa-broadcast-btn"
          style={{
          background: sent ? 'rgba(34,197,94,0.3)' : sending ? 'rgba(37,99,235,0.4)' : 'linear-gradient(135deg,rgba(37,99,235,0.8),rgba(255,153,51,0.8))',
          border: '1px solid ' + (sent ? 'rgba(34,197,94,0.5)' : 'rgba(37,99,235,0.5)'),
          cursor: (sending || !msg.trim() || (whatsapp && phone.length !== 10)) ? 'not-allowed' : 'pointer',
          opacity: (!msg.trim() || (whatsapp && phone.length !== 10)) ? 0.5 : 1,
        }}>
          {sending ? '⏳ Broadcasting...' : sent ? '✅ Announcement Sent!' : '📢 Broadcast Announcement'}
        </button>
      </div>

      {/* Recent log */}
      <div className="glass" style={{padding:20}}>
        <div className="pa-section-label">🕐 Recent Broadcasts</div>
        <div className="pa-log-list">
          {log.map((b, i) => (
            <div key={i} className="glass-sm" style={{padding:'10px 14px', display:'flex',
              justifyContent:'space-between', alignItems:'flex-start',
              background: b.fresh ? 'rgba(34,197,94,0.06)' : 'rgba(255,255,255,0.02)',
              border: b.fresh ? '1px solid rgba(34,197,94,0.2)' : '1px solid rgba(255,255,255,0.06)',
              animation: b.fresh ? 'fadeIn 0.3s ease' : 'none'}}>
              <div style={{flex:1, marginRight:10}}>
                <div style={{fontSize:12, fontWeight:500, color: b.fresh ? '#86efac' : '#cbd5e1', marginBottom:3}}>
                  {b.msg.length > 90 ? b.msg.substring(0,90) + '...' : b.msg}
                </div>
                <div style={{fontSize:10, color:'#7f93ad'}}>{b.ch} · {b.lang}</div>
              </div>
              <div style={{fontSize:11, color:'#7f93ad', whiteSpace:'nowrap'}}>{b.time}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <div style={{position:'fixed', bottom:24, right:24, zIndex:9999,
          background:'rgba(10,13,21,0.95)', border:'1px solid rgba(34,197,94,0.4)',
          borderRadius:12, padding:'12px 20px', color:'#86efac',
          fontSize:13, fontWeight:600, fontFamily:'Outfit,sans-serif',
          boxShadow:'0 8px 32px rgba(0,0,0,0.5)', display:'flex', alignItems:'center', gap:8,
          animation:'slideInRight 0.3s ease'}}>
          {toast}
        </div>
      )}
      </div>
    </PageLayout>
  )
}
