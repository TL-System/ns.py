graph [
  DateObtained "20/10/10"
  GeoLocation "Azerbaijan"
  GeoExtent "Country"
  Network "Azrena"
  Provenance "Primary"
  Access 0
  Source "http://www.azrena.org/about_en.htm"
  Version "1.0"
  DateType "Current"
  Type "REN"
  Backbone 1
  Commercial 0
  label "Azrena"
  ToolsetVersion "0.3.34dev-20120328"
  Customer 1
  IX 0
  SourceGitVersion "e278b1b"
  DateModifier "="
  DateMonth "10"
  LastAccess "20/10/10"
  Layer "IP"
  Creator "Topology Zoo Toolset"
  Developed 0
  Transit 0
  NetworkDate "2010_10"
  DateYear "2010"
  LastProcessed "2011_09_01"
  Testbed 0
  node [
    id 0
    label "None"
    Internal 1
    type "Switch"
  ]
  node [
    id 1
    label "Dialup server"
    Internal 1
    type "Switch"
  ]
  node [
    id 2
    label "Wireless server"
    Internal 1
    type "Router"
  ]
  node [
    id 3
    label "Wireless router"
    Internal 1
    type "Router"
  ]
  node [
    id 4
    label "Geology"
    Internal 1
    type "Switch"
  ]
  node [
    id 5
    label "Physics"
    Internal 1
    type "Switch"
  ]
  node [
    id 6
    label "ANAS users"
    Internal 0
  ]
  node [
    id 7
    label "Distribution switch"
    Internal 1
    type "Switch"
  ]
  node [
    id 8
    label "Information Tech."
    Internal 1
  ]
  node [
    id 9
    label "Baku Uni"
    Internal 1
  ]
  node [
    id 10
    label "Shamsa Obs."
    Internal 1
  ]
  node [
    id 11
    label "Cybenetics"
    Internal 1
  ]
  node [
    id 12
    label "Khazar Uni"
    Internal 1
  ]
  node [
    id 13
    label "NOC"
    Internal 1
    type "Router"
  ]
  node [
    id 14
    label "Economical Uni"
    Internal 1
    type "Router"
  ]
  node [
    id 15
    label "Local ISP"
    Internal 0
  ]
  node [
    id 16
    label "Silk Highway"
    Internal 0
  ]
  node [
    id 17
    label "VSAT Station"
    Internal 1
    type "Router"
  ]
  node [
    id 18
    label "Technical Uni"
    Internal 1
  ]
  node [
    id 19
    label "RENASCENE"
    Internal 1
  ]
  node [
    id 20
    label "Architecture-Building Uni"
    Internal 1
  ]
  node [
    id 21
    label "Foreign Language Uni."
    Internal 1
  ]
  edge [
    source 0
    target 1
    LinkType "Ethernet"
    LinkLabel "Ethernet"
  ]
  edge [
    source 0
    target 2
    LinkType "Ethernet"
    LinkLabel "Ethernet"
  ]
  edge [
    source 0
    target 3
    LinkType "Ethernet"
    LinkLabel "Ethernet"
  ]
  edge [
    source 0
    target 13
    LinkType "Ethernet"
    LinkLabel "Ethernet"
  ]
  edge [
    source 0
    target 7
    LinkType "Ethernet"
    LinkLabel "Ethernet"
  ]
  edge [
    source 1
    target 6
    LinkType "Serial"
    LinkLabel "Serial"
  ]
  edge [
    source 1
    target 6
    LinkType "Serial"
    LinkLabel "Serial"
  ]
  edge [
    source 1
    target 6
    LinkType "Serial"
    LinkLabel "Serial"
  ]
  edge [
    source 2
    target 18
    LinkType "Wireless"
    LinkLabel "wireless"
  ]
  edge [
    source 2
    target 19
    LinkType "Wireless"
    LinkLabel "Wireless"
  ]
  edge [
    source 2
    target 20
    LinkType "Wireless"
    LinkLabel "wireless"
  ]
  edge [
    source 3
    target 12
    LinkType "Wireless"
    LinkLabel "wireless"
  ]
  edge [
    source 3
    target 21
    LinkType "Wireless"
    LinkLabel "Wireless"
  ]
  edge [
    source 4
    target 7
    LinkType "Fiber"
    LinkLabel "fiber"
  ]
  edge [
    source 5
    target 7
    LinkType "Fiber"
    LinkLabel "fiber"
  ]
  edge [
    source 7
    target 8
    LinkType "Fiber"
    LinkLabel "fiber"
  ]
  edge [
    source 8
    target 9
    LinkType "Fiber"
    LinkLabel "fiber"
  ]
  edge [
    source 8
    target 10
    LinkType "Ethernet"
    LinkLabel "ethernet"
  ]
  edge [
    source 8
    target 11
    LinkType "Ethernet"
    LinkLabel "ethernet"
  ]
  edge [
    source 13
    target 17
    LinkType "Ethernet"
    LinkLabel "Ethernet"
  ]
  edge [
    source 13
    target 14
    LinkType "Serial"
    LinkLabel "serial"
  ]
  edge [
    source 13
    target 15
    LinkType "Serial"
    LinkLabel "serial"
  ]
  edge [
    source 13
    target 15
    LinkType "Serial"
    LinkLabel "Serial"
  ]
  edge [
    source 13
    target 15
    LinkType "Serial"
    LinkLabel "Serial"
  ]
  edge [
    source 16
    target 17
    LinkType "Serial"
    LinkLabel "serial"
  ]
]
