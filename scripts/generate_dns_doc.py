#!/usr/bin/env python3
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def create_document():
    doc = docx.Document()

    # Page Margins
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Colors
    PRIMARY_COLOR = RGBColor(24, 76, 120)     # Navy Blue
    SECONDARY_COLOR = RGBColor(52, 116, 172)  # Medium Blue
    TEXT_COLOR = RGBColor(51, 51, 51)         # Dark Gray
    MUTED_COLOR = RGBColor(102, 102, 102)     # Muted Gray
    SUCCESS_COLOR = RGBColor(22, 101, 52)     # Green
    WARNING_COLOR = RGBColor(154, 52, 18)     # Amber/Orange

    # Helper: Set font
    def set_font(run, font_name="Calibri", size_pt=11, color=TEXT_COLOR, bold=False, italic=False):
        run.font.name = font_name
        run.font.size = Pt(size_pt)
        run.font.color.rgb = color
        run.bold = bold
        run.italic = italic

    # Helper: Add Heading 1
    def add_h1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        set_font(run, "Calibri", 18, PRIMARY_COLOR, bold=True)
        return p

    # Helper: Add Heading 2
    def add_h2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        set_font(run, "Calibri", 14, SECONDARY_COLOR, bold=True)
        return p

    # Helper: Add Heading 3
    def add_h3(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        set_font(run, "Calibri", 12, PRIMARY_COLOR, bold=True)
        return p

    # Helper: Add Body Paragraph
    def add_body(text, bold_prefix="", space_after=6):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            run_b = p.add_run(bold_prefix)
            set_font(run_b, "Calibri", 11, TEXT_COLOR, bold=True)
        run = p.add_run(text)
        set_font(run, "Calibri", 11, TEXT_COLOR)
        return p

    # Helper: Add Code Block
    def add_code_block(code_text):
        table = doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False
        cell = table.cell(0, 0)
        cell.width = Inches(6.5)

        # Background color light gray
        shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="F4F6F8"/>')
        cell._tc.get_or_add_tcPr().append(shading)

        # Border light blue/gray
        borders = parse_xml(f'''
            <w:tcBorders {nsdecls("w")}>
                <w:top w:val="single" w:sz="4" w:space="0" w:color="D0D7DE"/>
                <w:left w:val="single" w:sz="18" w:space="0" w:color="184C78"/>
                <w:bottom w:val="single" w:sz="4" w:space="0" w:color="D0D7DE"/>
                <w:right w:val="single" w:sz="4" w:space="0" w:color="D0D7DE"/>
            </w:tcBorders>
        ''')
        cell._tc.get_or_add_tcPr().append(borders)

        cp = cell.paragraphs[0]
        cp.paragraph_format.space_before = Pt(4)
        cp.paragraph_format.space_after = Pt(4)
        cp.paragraph_format.line_spacing = 1.05
        run = cp.add_run(code_text)
        set_font(run, "Consolas", 9.5, RGBColor(33, 37, 41))

        # Add small spacing after table
        sp = doc.add_paragraph()
        sp.paragraph_format.space_before = Pt(0)
        sp.paragraph_format.space_after = Pt(4)

    # Helper: Add Callout Box
    def add_callout(title, text, is_success=True):
        table = doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False
        cell = table.cell(0, 0)
        cell.width = Inches(6.5)

        fill_color = "EBF7EE" if is_success else "FFFBEB"
        border_color = "166534" if is_success else "B45309"
        title_color = SUCCESS_COLOR if is_success else WARNING_COLOR

        shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_color}"/>')
        cell._tc.get_or_add_tcPr().append(shading)

        borders = parse_xml(f'''
            <w:tcBorders {nsdecls("w")}>
                <w:top w:val="none"/>
                <w:left w:val="single" w:sz="24" w:space="0" w:color="{border_color}"/>
                <w:bottom w:val="none"/>
                <w:right w:val="none"/>
            </w:tcBorders>
        ''')
        cell._tc.get_or_add_tcPr().append(borders)

        cp = cell.paragraphs[0]
        cp.paragraph_format.space_before = Pt(4)
        cp.paragraph_format.space_after = Pt(2)
        run_t = cp.add_run(title + "\n")
        set_font(run_t, "Calibri", 11, title_color, bold=True)

        run = cp.add_run(text)
        set_font(run, "Calibri", 10.5, TEXT_COLOR)

        sp = doc.add_paragraph()
        sp.paragraph_format.space_before = Pt(0)
        sp.paragraph_format.space_after = Pt(4)

    # -------------------------------------------------------------
    # DOCUMENT HEADER / TITLE
    # -------------------------------------------------------------
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(2)
    run_title = title_p.add_run("Suraksha CrowdVision")
    set_font(run_title, "Calibri", 26, PRIMARY_COLOR, bold=True)

    subtitle_p = doc.add_paragraph()
    subtitle_p.paragraph_format.space_before = Pt(0)
    subtitle_p.paragraph_format.space_after = Pt(16)
    run_sub = subtitle_p.add_run("DNS Configuration, Network Routing & Setup Guide")
    set_font(run_sub, "Calibri", 14, SECONDARY_COLOR)

    # Meta Table
    meta_table = doc.add_table(rows=4, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_table.autofit = False
    col_widths = [Inches(2.0), Inches(4.5)]
    meta_data = [
        ("Configured Domain Name", "crowdvision-dashboard.local (and Crowdvision-dashboard)"),
        ("Server IP Address", "10.54.23.55 (enx00e04c187718) / 192.168.3.199 (eno1)"),
        ("Cluster / Ingress Platform", "K3s Kubernetes with Traefik Ingress Controller"),
        ("Date & Status", "October 2026 | Active & Verified 24/7 (systemd service)")
    ]
    for row_idx, (k, v) in enumerate(meta_data):
        row = meta_table.rows[row_idx]
        for c_idx, text in enumerate([k, v]):
            cell = row.cells[c_idx]
            cell.width = col_widths[c_idx]
            shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{"F8FAFC" if row_idx%2==0 else "FFFFFF"}"/>')
            cell._tc.get_or_add_tcPr().append(shd)
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(3)
            run = p.add_run(text)
            set_font(run, "Calibri", 10, PRIMARY_COLOR if c_idx == 0 else TEXT_COLOR, bold=(c_idx == 0))

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # -------------------------------------------------------------
    # SECTION 1: EXECUTIVE SUMMARY & ACCESS URLS
    # -------------------------------------------------------------
    add_h1("1. Executive Summary & Access URLs")
    add_body(
        "To allow team members and stakeholders across the office network to easily access the CrowdVision dashboard without having to memorize or type raw IP addresses, a local network DNS name has been configured.",
        bold_prefix="Overview: "
    )

    add_callout(
        "Primary Office Access URL (Zero Configuration Required):",
        "http://crowdvision-dashboard.local/\n"
        "(Also accessible as http://Crowdvision-dashboard.local/)\n"
        "• Works out of the box across Windows 10/11, macOS, Linux, and iOS devices on office Wi-Fi / LAN.\n"
        "• All API endpoints, Swagger Docs, and WebSockets route seamlessly under this domain.",
        is_success=True
    )

    add_body(
        "In addition to the zero-configuration mDNS URL, colleagues can also use the exact short name http://crowdvision-dashboard/ via a quick office router DNS entry or local hosts mapping (detailed in Section 5).",
        space_after=8
    )

    # -------------------------------------------------------------
    # SECTION 2: HOW THE DNS WAS CONFIGURED
    # -------------------------------------------------------------
    add_h1("2. How the DNS Was Configured")
    add_body(
        "DNS resolution in a local office network operates differently than public internet domains (.com/.org). To achieve immediate, frictionless connectivity across team computers without requiring domain purchase or public certificate authorities, we implemented a three-tier architecture:",
        space_after=6
    )

    add_h3("Tier 1: Multicast DNS Daemon (Avahi / RFC 6762)")
    add_body(
        "The underlying Ubuntu Linux host runs avahi-daemon, which listens on UDP port 5353. Avahi implements mDNS (Zero-Configuration Networking / Bonjour). Any computer on the same local subnet querying for '*.local' domains receives an immediate direct response from Avahi with the host IP."
    )

    add_h3("Tier 2: Dynamic IP Auto-Detection Wrapper (publish_mdns.sh)")
    add_body(
        "Instead of hardcoding a single static IP address that breaks if DHCP reassigns a new IP address upon system reboot, we implemented an automated wrapper script at /home/user/k3s/Suraksha-deployment/scripts/publish_mdns.sh. This script queries the active network routing table (ip -4 route get 1.1.1.1) to dynamically detect the server's current IP address and broadcasts it to Avahi."
    )

    add_h3("Tier 3: Persistent Background Systemd User Service")
    add_body(
        "A systemd service named crowdvision-mdns.service was created under ~/.config/systemd/user/. To guarantee that the broadcast runs 24/7 across server reboots—even when no user is interactively logged in via terminal or desktop—we enabled systemd user lingering (loginctl enable-linger user). The service is configured with Restart=always to recover automatically from any transient network interruptions."
    )

    # -------------------------------------------------------------
    # SECTION 3: EXACT COMMANDS USED
    # -------------------------------------------------------------
    add_h1("3. Exact Commands Used")
    add_body("Below is the complete sequence of commands used to implement, register, and verify the DNS configuration:")

    add_h2("Step 3.1: Created the Dynamic IP Detection Script")
    add_body("File location: /home/user/k3s/Suraksha-deployment/scripts/publish_mdns.sh")
    add_code_block(
        "#!/usr/bin/env bash\n"
        "# Auto-detect current active network IP address\n"
        "PRIMARY_IP=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}')\n\n"
        "# Fallback to network adapter if routing check fails\n"
        "if [ -z \"$PRIMARY_IP\" ]; then\n"
        "    PRIMARY_IP=$(ip -4 -o addr show dev enx00e04c187718 2>/dev/null | awk '{print $4}' | cut -d/ -f1)\n"
        "fi\n\n"
        "if [ -z \"$PRIMARY_IP\" ]; then\n"
        "    PRIMARY_IP=\"10.54.23.55\"\n"
        "fi\n\n"
        "echo \"Publishing mDNS: crowdvision-dashboard.local -> ${PRIMARY_IP}\"\n"
        "exec /usr/bin/avahi-publish-address -a crowdvision-dashboard.local \"${PRIMARY_IP}\" -R -f"
    )

    add_body("Made the script executable:")
    add_code_block("chmod +x /home/user/k3s/Suraksha-deployment/scripts/publish_mdns.sh")

    add_h2("Step 3.2: Created the Persistent Systemd User Service")
    add_body("File location: ~/.config/systemd/user/crowdvision-mdns.service")
    add_code_block(
        "[Unit]\n"
        "Description=Avahi mDNS Publisher for crowdvision-dashboard.local (Auto-detects IP)\n"
        "After=network.target network-online.target\n"
        "Wants=network-online.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        "ExecStart=/home/user/k3s/Suraksha-deployment/scripts/publish_mdns.sh\n"
        "Restart=always\n"
        "RestartSec=5\n\n"
        "[Install]\n"
        "WantedBy=default.target"
    )

    add_h2("Step 3.3: Enabled Systemd Lingering & Started the Service")
    add_body("These commands enable 24/7 background operation independent of user terminal sessions and launch the service:")
    add_code_block(
        "# Enable persistent lingering so background user services run across reboots and logouts\n"
        "loginctl enable-linger user\n\n"
        "# Reload systemd daemon to pick up the new service\n"
        "systemctl --user daemon-reload\n\n"
        "# Enable the service on system startup and start it immediately\n"
        "systemctl --user enable --now crowdvision-mdns.service\n\n"
        "# Verify service status\n"
        "systemctl --user status crowdvision-mdns.service"
    )

    add_h2("Step 3.4: Verification Commands")
    add_body("We verified local and network resolution with the following diagnostic commands:")
    add_code_block(
        "# 1. Resolve host using Name Service Switch (NSS):\n"
        "getent ahosts crowdvision-dashboard.local\n"
        "# Output: 10.54.23.55 STREAM crowdvision-dashboard.local\n\n"
        "# 2. Ping verification:\n"
        "ping -c 2 crowdvision-dashboard.local\n"
        "# Output: 64 bytes from surakshaai (10.54.23.55): icmp_seq=1 ttl=64 time=0.037 ms\n\n"
        "# 3. Ingress HTTP verification:\n"
        "curl -I http://crowdvision-dashboard.local/\n"
        "# Output: HTTP/1.1 200 OK\n\n"
        "# 4. Backend API verification:\n"
        "curl -s http://crowdvision-dashboard.local/api/health/simple\n"
        "# Output: {\"status\":\"ok\",\"timestamp\":\"2026-10-08T...\"}"
    )

    # -------------------------------------------------------------
    # SECTION 4: WHERE THE DNS NAME WAS ADDED IN THE CODE
    # -------------------------------------------------------------
    add_h1("4. Where Was the DNS Name Added in the Code?")
    add_body(
        "Important Architectural Insight: The DNS name was deliberately NOT hardcoded into the application code or frontend JavaScript files. This design ensures the application remains modular, cloud-native, and production-ready.",
        bold_prefix="Architectural Principle: "
    )
    add_body("Here is why no code changes were necessary and how each layer automatically handles the new DNS name:")

    add_h3("1. Kubernetes Traefik Ingress (Catch-All Routing)")
    add_body(
        "In k3s/stack/base/ingress.yaml and the deployed Ingress resource, the HTTP routing rules do not define a restrictive 'host:' property. Instead, Traefik uses path-based rules:\n"
        "• Path '/' routes to crowdvision-frontend service\n"
        "• Paths '/api', '/docs', '/openapi.json', and '/redoc' route to crowdvision-backend service\n"
        "Because there is no host restriction, Traefik matches ANY incoming Host header (whether 10.54.23.55, crowdvision-dashboard.local, or crowdvision-dashboard) and routes it cleanly."
    )

    add_h3("2. Frontend API Configuration (Relative Origin Routing)")
    add_body(
        "In Crowd_Vision_Frontend/.env, the API endpoint is configured as:\n"
        "    VITE_API_URL=/api\n"
        "Because this path is relative (no hardcoded IP or domain prefix), modern web browsers automatically send all API calls to the same origin (protocol, host, and port) that loaded the page. When a user opens http://crowdvision-dashboard.local/, the browser automatically routes all API queries to http://crowdvision-dashboard.local/api/ without any client-side reconfiguration."
    )

    add_h3("3. Dynamic WebSocket Resolution (websocketService.ts)")
    add_body(
        "In Crowd_Vision_Frontend/src/services/websocketService.ts (lines 17–19):\n"
        "    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';\n"
        "    const cleanPath = apiUrl.replace(/\\/api$/, '');\n"
        "    return `${protocol}//${window.location.host}${cleanPath}`;\n"
        "The WebSocket service dynamically reads window.location.host from the browser runtime. Whether users access via IP, .local domain, or custom intranet DNS, WebSockets for live video analytics and crowd counts connect seamlessly."
    )

    # -------------------------------------------------------------
    # SECTION 5: IF THE IP CHANGES, WILL THE DNS BE THE SAME?
    # -------------------------------------------------------------
    add_h1("5. If the IP Changes, Will the DNS Be the Same? (YES / NO)")

    add_callout(
        "DIRECT ANSWER:",
        "1. DNS Name for Users: YES\n"
        "   The URL and DNS name (http://crowdvision-dashboard.local/) remains 100% THE SAME for all colleagues in your office. Users never need to learn a new link.\n\n"
        "2. IP Resolution Under the Hood: YES (Automatically Handled via Script)\n"
        "   Because we created the dynamic publish_mdns.sh script, when the server restarts or obtains a new IP address via DHCP, the service automatically detects the new IP and broadcasts it under the same DNS name.",
        is_success=True
    )

    add_body(
        "Below is a comparison of how different DNS methods behave when the server's network IP address changes:",
        space_after=8
    )

    # Comparison Table
    table = doc.add_table(rows=4, cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    col_w = [Inches(1.5), Inches(1.2), Inches(1.6), Inches(2.2)]
    headers = ["DNS Method", "URL Used", "If IP Changes, Same DNS?", "Action Required on IP Change"]
    for i, h in enumerate(headers):
        cell = table.cell(0, i)
        cell.width = col_w[i]
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="184C78"/>')
        cell._tc.get_or_add_tcPr().append(shd)
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(h)
        set_font(run, "Calibri", 10, RGBColor(255, 255, 255), bold=True)

    rows_data = [
        ("mDNS (Avahi Service)\n[Currently Active]", "http://crowdvision-dashboard.local/", "YES\n(Automatic)", "NONE. Our dynamic script automatically detects and broadcasts the new IP on startup."),
        ("Office Router / DNS Server (A Record)", "http://crowdvision-dashboard/", "YES (Name stays same)\nIP Mapping: Manual", "Network Admin updates the A-Record on router OR sets a DHCP Static Reservation."),
        ("Client hosts file\n(Individual PCs)", "http://crowdvision-dashboard/", "YES (Name stays same)\nIP Mapping: Manual", "Colleagues must update the IP address line in their local hosts file.")
    ]

    for row_idx, r in enumerate(rows_data, start=1):
        for col_idx, text in enumerate(r):
            cell = table.cell(row_idx, col_idx)
            cell.width = col_w[col_idx]
            shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{"F8FAFC" if row_idx%2==0 else "FFFFFF"}"/>')
            cell._tc.get_or_add_tcPr().append(shd)
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(4)
            run = p.add_run(text)
            set_font(run, "Calibri", 9.5, TEXT_COLOR)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    add_callout(
        "Best Practice Recommendation for IT/Network Administration:",
        "To ensure the server IP never unexpectedly shifts in the office:\n"
        "Ask your office network administrator to set a DHCP Static Reservation (MAC Binding) on the office router for this workstation's MAC address (00:e0:4c:18:77:18) to lock IP 10.54.23.55 permanently.",
        is_success=False
    )

    # -------------------------------------------------------------
    # SECTION 6: INSTRUCTIONS FOR OFFICE COLLEAGUES
    # -------------------------------------------------------------
    add_h1("6. Sharing with Office Colleagues")
    add_body("You can share the instructions below with your team members depending on their preferred access method:")

    add_h2("Method 1: Instant Access via Browser (No Setup Required)")
    add_body("Send colleagues this link directly in email, Slack, or Teams:")
    add_code_block("http://crowdvision-dashboard.local/")
    add_body(
        "Supported Out-of-the-Box:\n"
        "• Windows 10 & Windows 11 (mDNS enabled by default)\n"
        "• Apple macOS (MacBooks / iMacs via Bonjour)\n"
        "• Apple iPhones / iPads (Safari & Chrome)\n"
        "• Linux Desktops (Ubuntu, Fedora, etc. via Avahi)"
    )

    add_h2("Method 2: Using the Short Name (http://crowdvision-dashboard/)")
    add_body("If colleagues prefer omitting the '.local' suffix, use either of the options below:")

    add_h3("Option A: Office Router DNS (One-time setup for the entire company)")
    add_body(
        "Your office IT administrator adds an internal DNS entry on the Wi-Fi router / DHCP server:\n"
        "    Hostname: crowdvision-dashboard\n"
        "    IP Address: 10.54.23.55\n"
        "Result: Every computer connected to office Wi-Fi can open http://crowdvision-dashboard/ immediately."
    )

    add_h3("Option B: Individual PC hosts File Configuration")
    add_body(
        "For specific computers without router configuration:\n"
        "1. Windows: Open Notepad as Administrator -> Open C:\\Windows\\System32\\drivers\\etc\\hosts\n"
        "   Add line: 10.54.23.55    crowdvision-dashboard\n"
        "2. macOS / Linux: Run 'sudo nano /etc/hosts' in Terminal\n"
        "   Add line: 10.54.23.55    crowdvision-dashboard\n"
        "Save and exit. The short name http://crowdvision-dashboard/ will resolve instantly."
    )

    # -------------------------------------------------------------
    # SECTION 7: AUTO-START & POWER-LOSS RECOVERY CONFIGURATION
    # -------------------------------------------------------------
    add_h1("7. System Startup & Power-Loss Recovery Configuration")
    add_body(
        "To guarantee that K3s and the CrowdVision application start automatically whenever the workstation powers on or restarts—including recovery after an unexpected power outage—the full startup chain has been verified and configured:",
        bold_prefix="Continuous Availability: "
    )

    add_callout(
        "Auto-Start Status Verification:",
        "• k3s.service: ENABLED (systemctl enable k3s.service)\n"
        "• mongod.service: ENABLED (MongoDB database starts at boot)\n"
        "• crowdvision-mdns.service: ENABLED (mDNS domain publisher with user linger)\n"
        "• All Pods: restartPolicy: Always and imagePullPolicy: Never (Instant local boot)",
        is_success=True
    )

    add_h2("7.1: Software Auto-Start Chain")
    add_body(
        "1. Operating System Boot: When Ubuntu starts, systemd initiates multi-user.target.\n"
        "2. Database: mongod.service launches automatically.\n"
        "3. Kubernetes Engine: k3s.service launches containerd, Flannel CNI, and the Traefik Ingress controller.\n"
        "4. Workloads: StatefulSet (crowdvision-backend-0, crowdvision-backend-1), Deployment (crowdvision-frontend), and MediaMTX are restored with state 'Running'.\n"
        "5. Domain Broadcasting: crowdvision-mdns.service auto-detects the active network IP and publishes 'crowdvision-dashboard.local'."
    )

    add_h2("7.2: Hardware / Power-Cut Recovery (BIOS Setting)")
    add_body(
        "To ensure the HP Z6 G4 Workstation automatically turns back on if electricity is cut and then restored:\n"
        "1. Power on the machine and press F10 during boot to enter BIOS Setup.\n"
        "2. Navigate to: Advanced -> Power Management Options -> After Power Loss.\n"
        "3. Select: 'Power On' (or 'Previous State').\n"
        "4. Press F10 to Save and Exit.\n"
        "With this setting enabled, whenever electricity returns, the computer automatically powers on, boots Ubuntu, starts K3s, and runs the application completely unattended."
    )

    # Save document
    output_path = "/home/user/k3s/Suraksha-deployment/DNS-config.docx"
    doc.save(output_path)
    print(f"Document saved successfully at: {output_path}")

if __name__ == "__main__":
    create_document()
