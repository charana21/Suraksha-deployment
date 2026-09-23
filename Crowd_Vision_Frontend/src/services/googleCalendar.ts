// Google Calendar API integration for fetching public Indian holiday events
// The API key is for public calendar access only (publishable)
// Falls back to built-in events if not configured
const ENV_MAP = (typeof import.meta !== "undefined"
    ? (import.meta.env as unknown as Record<string, unknown>)
    : {}) as Record<string, unknown>;

export const GOOGLE_CALENDAR_API_KEY =
    (typeof ENV_MAP.VITE_GOOGLE_CALENDAR_API_KEY === "string" && ENV_MAP.VITE_GOOGLE_CALENDAR_API_KEY.trim()
        ? ENV_MAP.VITE_GOOGLE_CALENDAR_API_KEY
        : "AIzaSyCh7OpC1gDxWZ3cAr6BQNZE0litXEv9O");


// Indian holidays calendar ID (public Google Calendar)
const INDIAN_HOLIDAYS_CALENDAR_ID = "en.indian%23holiday%40group.v.calendar.google.com";

export interface GoogleCalendarEvent {
    id: string;
    summary: string;
    start: { date?: string; dateTime?: string };
    end: { date?: string; dateTime?: string };
    description?: string;
}

type FixedHoliday = { date: string; name: string };

export const FIXED_KEY_EVENTS_2026: FixedHoliday[] = [
    { date: "2026-01-01", name: "New Year's Day" },
    { date: "2026-01-14", name: "Makar Sankranti / Pongal" }, 
    { date: "2026-01-26", name: "Republic Day" },              
    { date: "2026-02-14", name: "Valentine's Day" },
    { date: "2026-02-15", name: "Maha Shivratri" },            
    { date: "2026-03-03", name: "Holika Dahan" },              
    { date: "2026-03-04", name: "Holi" },                       
    { date: "2026-03-19", name: "Gudi Padwa / Ugadi" },        
    { date: "2026-03-21", name: "Eid ul-Fitr" },               
    { date: "2026-03-26", name: "Ram Navami" },                
    { date: "2026-04-03", name: "Good Friday" },               
    { date: "2026-04-14", name: "Ambedkar Jayanti" },
    { date: "2026-05-01", name: "Labour Day / Buddha Purnima" }, 
    { date: "2026-05-27", name: "Eid ul-Adha (Bakrid)" },       
    { date: "2026-06-26", name: "Muharram" },                  
    { date: "2026-08-15", name: "Independence Day" },
    { date: "2026-08-26", name: "Onam (Thiruvonam)" },         
    { date: "2026-08-28", name: "Raksha Bandhan" },            
    { date: "2026-09-04", name: "Janmashtami" },               
    { date: "2026-09-05", name: "Teacher's Day (India)" },
    { date: "2026-09-14", name: "Ganesh Chaturthi" },          
    { date: "2026-10-02", name: "Gandhi Jayanti" },
    { date: "2026-10-05", name: "World Teacher's Day" },
    { date: "2026-10-11", name: "Navratri Begins" },           
    { date: "2026-10-20", name: "Dussehra" },                  
    { date: "2026-11-06", name: "Dhanteras" },                 
    { date: "2026-11-08", name: "Diwali (Lakshmi Puja)" },     
    { date: "2026-11-14", name: "Children's Day" },
    { date: "2026-11-15", name: "Chhath Puja" },               
    { date: "2026-11-24", name: "Guru Nanak Jayanti" },
    { date: "2026-12-25", name: "Christmas" },
    { date: "2026-12-31", name: "New Year's Eve" }
];

export const FIXED_KEY_EVENTS_2026_COUNT = FIXED_KEY_EVENTS_2026.length;

function addOrAppendEvent(
    target: Record<string, { name: string; color: string }>,
    dateStr: string,
    eventName: string
) {
    const existing = target[dateStr];
    if (!existing) {
        target[dateStr] = { name: eventName, color: getEventColor(eventName) };
        return;
    }

    const names = new Set(existing.name.split(" / ").map((x) => x.trim()).filter(Boolean));
    names.add(eventName);
    const mergedName = Array.from(names).join(" / ");
    target[dateStr] = { name: mergedName, color: getEventColor(mergedName) };
}

function getFixedKeyEventsMap(year: number): Record<string, { name: string; color: string }> {
    if (year !== 2026) return {};
    const map: Record<string, { name: string; color: string }> = {};
    FIXED_KEY_EVENTS_2026.forEach((e) => addOrAppendEvent(map, e.date, e.name));
    return map;
}

export const fetchGoogleCalendarEvents = async (
    year: number,
    apiKey: string
): Promise<Record<string, { name: string; color: string }>> => {
    const fixedEvents = getFixedKeyEventsMap(year);

    if (!apiKey) {
        return fixedEvents;
    }

    try {
        const timeMin = `${year}-01-01T00:00:00Z`;
        const timeMax = `${year}-12-31T23:59:59Z`;
        const url = `https://www.googleapis.com/calendar/v3/calendars/${INDIAN_HOLIDAYS_CALENDAR_ID}/events?key=${apiKey}&timeMin=${timeMin}&timeMax=${timeMax}&singleEvents=true&orderBy=startTime&maxResults=100`;

        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Google Calendar API error: ${response.status}`);
        }

        const data = await response.json();
        const events: Record<string, { name: string; color: string }> = {};

        (data.items || []).forEach((event: GoogleCalendarEvent) => {
            const dateStr = event.start.date || event.start.dateTime?.split("T")[0];
            if (dateStr && event.summary) {
                addOrAppendEvent(events, dateStr, event.summary);
            }
        });

        return { ...events, ...fixedEvents };
    } catch (error) {
        return fixedEvents;
    }
};

const getEventColor = (eventName: string): string => {
    const name = eventName.toLowerCase();
    if (name.includes("diwali") || name.includes("deepavali")) return "#f39c12";
    if (name.includes("holi") || name.includes("dussehra") || name.includes("holika")) return "#e74c3c";
    if (name.includes("eid") || name.includes("ramadan")) return "#16a085";
    if (name.includes("christmas") || name.includes("x-mas")) return "#c0392b";
    if (name.includes("navratri") || name.includes("durga")) return "#e74c3c";
    if (name.includes("ganesh") || name.includes("ganpati")) return "#e67e22";
    if (name.includes("independence") || name.includes("republic")) return "#27ae60";
    if (name.includes("shivratri") || name.includes("shivaratri")) return "#9b59b6";
    if (name.includes("janmashtami") || name.includes("krishna")) return "#8e44ad";
    if (name.includes("pongal") || name.includes("sankranti") || name.includes("lohri") || name.includes("gudi padwa") || name.includes("ugadi") || name.includes("dhanteras")) return "#f39c12";
    if (name.includes("onam")) return "#27ae60";
    if (name.includes("valentine")) return "#e91e63";
    if (name.includes("new year")) return "#9b59b6";
    if (name.includes("gandhi") || name.includes("muharram")) return "#2c3e50";
    if (name.includes("teacher's day") || name.includes("children's day") || name.includes("ambedkar")) return "#3498db";
    if (name.includes("raksha bandhan") || name.includes("ram navami") || name.includes("chhath puja") || name.includes("guru nanak")) return "#e67e22";
    if (name.includes("labour day") || name.includes("buddha purnima")) return "#c0392b";
    return "#7f8c8d";
};
