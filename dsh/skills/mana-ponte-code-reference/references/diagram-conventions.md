# Diagram Design Conventions for Network Equipment Visualizations

These conventions are derived from standard network equipment diagrams found in documentation, RFCs, and professional visualization tools (e.g., ConceptDraw, Creately, Wikimedia rack diagrams). They ground the SVG design to real-world visual expectations rather than overly complex or ambiguous layouts.

## Key Design Principles
1. **Standard 19" Rack Proportions**: Use typical rack height/width ratios (standard is ~18 inches tall x 24 inches wide)
2. **Clear Equipment Representation**: 
   - Servers: shown as simple rectangles with labeled heights to indicate different virtual tiers or server sizes
   - NAS: cylindrical or rectangular housing clearly distinguished from servers with indicator lights and port labels
3. **Top-Down/Side Elevation View**: Use a side elevation perspective that's easy to read in diagrams (not isometric which can be confusing)
4. **Minimal Clutter**: Avoid excessive detail; focus on the main elements requested: rack of internet equipment and NAS device
5. **Consistent Labeling**: Clear, concise labels for each component type (e.g., "Internet Rack", "NAS")
6. **Visual Hierarchy**: Use colors and spacing to guide the viewer's eye naturally through the diagram
7. **Grid Reference**: Include subtle grid lines or reference marks that help orient the view without overwhelming it

## Layout Guidelines for This Diagram
- Main element: A server rack (side elevation) occupying most of the diagram area with 3-4 evenly spaced rows representing virtual server tiers
- NAS device positioned prominently but appropriately relative to the rack (placed beside/slightly offset from the rear edge of the rack, shown as a simple cylindrical or rectangular housing)
- Equipment rows in the rack should be evenly spaced and clearly represent different virtual tiers without excessive detail
- Labels are placed outside the equipment elements using standard annotation conventions  
- Color palette: Use muted, professional colors appropriate for technical diagrams (dark gray background with white/light blue equipment boxes, NAS in a distinct but harmonious color like teal or soft blue)

This approach ensures the SVG is both technically meaningful and visually clear, avoiding overly complex shapes that made previous versions appear "too bad."