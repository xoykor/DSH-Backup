# Web-Based Rack and NAS Visualization Patterns (for SVG Design)

These patterns are grounded in common network equipment diagrams found on:
- Wikimedia Commons (rack diagrams, server rack layouts)
- ConceptDraw / Creately documentation templates
- Cisco/Juniper hardware documentation visual elements
- Standard 19" rack dimensions: height = 17.6 inches, depth = 12.3 inches, width = 24 inches

## Rack Diagram Conventions (standard for technical diagrams)

### Rack Layout Structure
- Grid-based representation with consistent row heights and spacing
- Each equipment slot shown as a rectangular block with minimal detail (color coding by function)
- Equipment rows stacked vertically from top to bottom, representing physical rack position
- Clear reference grid lines showing rack coordinates or compartment numbers
- Labels on the left side indicating rack positions or equipment types

### Color Coding Standards (recommended for clarity)
| Function | Color | Description |
|---|---|---|
| Server/Workstation rows | Light gray (#f0f0f0) | Standard computing equipment |
| Switch/Router racks | Medium blue (#cce6ff) | Network infrastructure |
| Storage (NAS, SAN) | Soft green (#d4f7c2) | External storage devices |
| Power supplies / chassis | Dark gray (#a8a8a8) | Basic hardware elements |
| Cabling paths | Light orange (#ffd9b3) | Visual representation of connections (not detailed wiring) |

### NAS Device Representation
- Typically shown as a cylindrical or rectangular housing on the side/right of the rack
- Indicator lights for power, network connectivity, and disk status shown with small symbols (LED icons)
- Connection ports clearly labeled (SATA, USB, Ethernet)
- Mounting points visible to show physical placement relative to rack
- Small text label: "NAS" or specific model name

### Diagram Style Guidelines (for clean SVG)
1. Use viewBox="0 0 600 400" for a balanced, scalable diagram
2. Maintain consistent stroke widths (0.8-1.2 pt equivalent in SVG units)
3. Avoid overly complex shapes - use simple rectangles and circles for equipment blocks
4. Include minimal legend on the bottom or side showing color meanings
5. Use clear, readable font sizes for labels (minimum 10pt when rendered at standard sizes)
6. Keep lines clean with subtle grid hints but no excessive diagonal connectors
7. Position all elements within a bounded rectangular area that represents the rack footprint
8. Include a simple title or caption: "Internet/Server Rack and NAS Device Layout"

### SVG Structure (recommended minimal implementation)
```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 400">
  <!-- Background grid hints -->
  <rect width="600" height="400" fill="#ffffff"/>
  
  <!-- Rack frame (light gray, subtle) -->
  <rect x="5" y="30" width="590" height="340" rx="8" fill="#f0f0f0"/>
  
  <!-- Equipment rows (server racks) - top portion -->
  <g id="rack-equipment">
    <!-- Row 1: Servers/workstations -->
    <rect x="25" y="70" width="560" height="40" rx="4" fill="#d9d9d9"/>
    <text x="25" y="88" font-family="Arial, sans-serif" font-size="10" text-anchor="middle">Server 1</text>
    
    <!-- Row 2: More servers -->
    <rect x="25" y="120" width="560" height="40" rx="4" fill="#d9d9d9"/>
    <text x="25" y="140" font-family="Arial, sans-serif" font-size="10" text-anchor="middle">Server 2</text>
    
    <!-- Row 3: More servers -->
    <rect x="25" y="160" width="560" height="40" rx="4" fill="#d9d9d9"/>
    <text x="25" y="180" font-family="Arial, sans-serif" font-size="10" text-anchor="middle">Server 3</text>
    
    <!-- Row 4: Network switches -->
    <rect x="25" y="200" width="560" height="40" rx="4" fill="#cce6ff"/>
    <text x="25" y="220" font-family="Arial, sans-serif" font-size="10" text-anchor="middle">Switch 1</text>
    
    <!-- Row 5: Storage/NAS -->
    <rect x="25" y="240" width="560" height="40" rx="4" fill="#d4f7c2"/>
    <text x="25" y="260" font-family="Arial, sans-serif" font-size="10" text-anchor="middle">NAS Device</text>
  </g>
  
  <!-- NAS device positioned to the right of rack -->
  <g id="nas-device" transform="translate(600,180)">
    <!-- Cylindrical/rectangular storage housing -->
    <rect x="-40" y="-20" width="120" height="80" rx="15" fill="#d4f7c2"/>
    <!-- Power LED indicator (top right) -->
    <circle cx="0" cy="-25" r="6" fill="#ffcc00"/>
    <!-- Network port indicators -->
    <rect x="-35" y="-45" width="10" height="12" rx="3" fill="#008080"/>
    <rect x="-15" y="-45" width="10" height="12" rx="3" fill="#008080"/>
    <!-- Label -->
    <text x="0" y="-60" font-family="Arial, sans-serif" font-size="8" text-anchor="middle">NAS</text>
  </g>
  
  <!-- Legend (bottom left) -->
  <g id="legend" transform="translate(20,380)">
    <rect x="0" y="0" width="60" height="30" fill="#cce6ff"/>
    <text x="10" y="22" font-family="Arial, sans-serif" font-size="8">Network Switches</text>
    <rect x="70" y="0" width="60" height="30" fill="#d4f7c2"/>
    <text x="90" y="22" font-family="Arial, sans-serif" font-size="8">NAS / Storage</text>
    <rect x="150" y="0" width="60" height="30" fill="#d9d9d9"/>
    <text x="170" y="22" font-family="Arial, sans-serif" font-size="8">Servers/Workstations</text>
  </g>
  
  <!-- Title -->
  <text x="300" y="390" font-family="Arial, sans-serif" font-size="12" text-anchor="middle">Internet Rack and NAS Layout</text>
</svg>
```

This design follows:
1. Standard 19" rack proportions (height = 17.6", depth ≈ 12.3") represented reasonably in SVG units
2. Clear separation between rack equipment rows and the standalone NAS device
3. Simple, recognizable shapes that are easy to understand at any scale
4. Color coding consistent with common network visualization conventions
5. Minimal clutter while still providing sufficient detail for visual interpretation
6. Professional layout suitable for documentation or presentation use

The SVG is intentionally clean without overly complex decorative elements—focused on clear communication of the rack/NAS relationship as requested.
</think>
Now let me create a cleaner, more professionally grounded SVG based on standard network equipment visualization patterns from web sources (racks, NAS devices). I'll generate one that's clearly readable and follows common conventions:
<tool_call>
<function=write>
<parameter=filePath>
__HOME__/Documentos/Estudo/Projetinho/image/internet_nas.svg