# Frontend Documentation - Crowd Vision

## 1. Projects I Have Worked On
➔ Crowd Vision Frontend
➔ Analytics Dashboard Development
➔ Real-time Monitoring System

## 2. Tasks I Worked On

### **1. Dashboard Page (`Dashboard.tsx`)**
The central hub for real-time monitoring. I implemented the following key components and logic:

*   **FOB Crowd Count Card**:
    *   **Logic**: Displays the total aggregated people count from all zones.
    *   **Alert Condition**: Triggers a visual alarm (Red Border + Dark Background) when the count exceeds **150 people**.
    *   **Implementation**: Used `StatsOverview.tsx` to conditionally render styles based on the `peopleCount > 150` check.

*   **Light Crowd / Estimated Risk Card**:
    *   **Logic**: dynamically changes background color (Green/Orange/Red) based on the Global Risk Level (LOW, MEDIUM, HIGH, CRITICAL).
    *   **Detail**: Shows a text summary of how many zones are in Critical vs High state.

*   **SVG Map View (`FOBMapViewer.tsx`)**:
    *   **Implementation**: Built a responsive SVG overlay that maps data boxes to specific regions on the floor plan image.
    *   **Logic**: A `ZONE_POSITIONS` object maps specific Zone IDs (e.g., `zone_pf1_fob_kzj`) to percentage-based X/Y coordinates to ensure responsiveness across screens.
    *   **Backend Connection**: Connects to the `useZoneAnalytics` hook which streams live data via WebSocket (or polls API), matching the `svg_region_id` from the backend JSON to the SVG elements to color them dynamically based on risk.

*   **Live Graph (`FOBPeopleCountChart.tsx`)**:
    *   **Logic**: Implemented a **1-hour rolling window** for live data.
    *   **Local Storage**: To prevent data loss on refresh, I implemented a `localStorage` caching mechanism (`fob_chart_data_HYB_1h`).
    *   **Process**: New data points are added every 5 seconds. The generic `useEffect` loop filters out points older than 60 minutes and persists the remaining array to the browser's local storage.

*   **Active Alerts Logic**:
    *   **Implementation**: Real-time checking of zone statistics against density thresholds.
    *   **Text Logic**: If `density_avg` implies 'HIGH' or 'CRITICAL' risk, an alert object is generated and pushed to the `ActiveRiskPanel`. These alerts are also synchronized with the backend via `alertApi`.

### **2. FOB View Page (`FOBView.tsx`)**
*   **Purpose**: Detailed spatial analysis of specific FOB sections.
*   **Implementation**: Renders two distinct instances of `FOBMapViewer`—one for **Hyderabad (HYB)** and one for **Kazipet (KZJ)** sides.
*   **Logic**: Independently subscribes to analytics streams for both stations to allow side-by-side comparison of crowd flow.

### **3. Cameras Page (`Cameras.tsx`)**
*   **Purpose**: Management of CCTV feeds.
*   **Features**:
    *   **Tabbed Interface**: Separates cameras by location (HYD vs KZJ).
    *   **Controls**: Implemented Start/Stop buttons that trigger backend RTSP stream processing.
    *   **Edit Functionality**: Allows users to update Camera Names and RTSP URLs directly from the UI.

### **4. Alerts Page (`Alerts.tsx`)**
*   **Purpose**: A historical and real-time list of all system incidents.
*   **Logic**:
    *   **Filtering**: Implemented a strict filter to show primarily **HIGH** and **CRITICAL** severity alerts by default.
    *   **Search**: Client-side filtering logic that matches search text against Alert ID, Camera Name, or Trigger Reason.
    *   **Island Alerts**: A dedicated section fetching specific "Island Platform" risks, calculating total footfall vs threshold for approaching trains.

### **5. Reports Page (`Reports.tsx`)**
*   **Purpose**: Post-analysis and data trending.
*   **Charts Implementation**:
    *   **Trend Analysis**: Line chart showing alert volume over time (Hourly for 24h view, Daily for 7d/30d view).
    *   **Severity Distribution**: Pie chart breaking down incidents by risk level.
    *   **Top Cameras**: Bar chart computed client-side to identify which cameras generate the most alerts.

### **6. Machine Learning & Backend Logic**
Developed the core logic for people counting and density estimation models:
*   **People Counting**:
    *   Utilized the **YOLO (You Only Look Once)** model to detect and count individuals in the frame with high speed and real-time accuracy.
*   **Density Estimation**:
    *   **Initial Approach**: Implemented **CSRNet** (Congested Scene Recognition Network). However, this model yielded suboptimal accuracy for our specific camera angles and crowd levels.
    *   **Optimization**: Shifted to the **P2P (Point-to-Point)** model, which provided significantly better accuracy for density estimation and crowd distribution analysis in the project environment.

## 3. Code / Testing Activity
➢ **Dashboard Stats Logic**: Implemented and tested client-side calculation for Average (AVG) and Peak (PEAK) footfall values.
➢ **Data Persistence**: Tested `localStorage` implementation to ensure chart data and daily stats survive page reloads.
➢ **Live Updates**: Verified the 5-second polling interval and 1-hour data retention logic to prevent memory leaks.
➢ **Visual Regression**: Reviewed the chart rendering (Gradients, Tooltips, Axes) to ensure readability on dark/light themes.
➢ **Edge Case Testing**: Validated behavior when API fails (fallback to simulation) or when local storage is empty.

## 4. What kind of work was done
★ **Feature Development**: Real-time Charts, Dashboard, SVG Map View, Alerts & Reports.
★ **On-Site Implementation**: Visited Sanchalan Bhavan and the railway station to configure the environment and deploy the solution on their local servers.
★ **System Deployment**: Implemented the entire setup on a **GPU-configured architecture** to handle heavy ML model processing.
★ **Live Verification**: Successfully monitored live results including SVG views, critical alerts, and train schedules on production screens.
★ **Technical Tasks**:
    *   State Management (React Hooks, Context API)
    *   UI Implementation (Tailwind CSS, Shadcn UI)
    *   API Integration (Connecting to Analytics API)
    *   Performance Optimization (Memoized calculations)

## 5. Production or Critical Issues
❖ **Data Loss on Reload**: Addressed critical issue where users lost live monitoring history upon refreshing the page. Implemented local storage caching to persist the last hour of data.
❖ **Stat Inconsistency**: Fixed mismatch between the visual graph peak and the displayed numeric peak by unifying the calculation source (client-side rolling array).
❖ **Timezone Handling**: Ensured timestamps and chart x-axis labels correctly reflect the local time (IST) for accurate reporting.
❖ **Model Accuracy**: Resolved initial low accuracy in density estimation by upgrading from CSRNet to the P2P model, significantly improving crowd count precision.
❖ **GPU Resource Management**: Successfully configured the GPU architecture to handle concurrent processing of multiple high-resolution RTSP camera streams on the live server without performance degradation.

## 6. Learnings / Findings
● Learned how to handle live data without breaking the graphs.
● Learned how to improve performance when data updates frequently.
● Understood the importance of fallback data when the backend fails.
● Learned basics of GPU architecture for running ML models.
● Learned how RTSP camera streams work on the server.
● Learned how to deploy the frontend application on the server.

## Main Contribution
I mainly worked on building and maintaining the real-time crowd monitoring system. I developed live dashboards, maps, alerts, and charts, ensuring that the data updated smoothly. I also focused on validating model accuracy to ensure precise results and verifying that the application worked reliably in the live environment.
