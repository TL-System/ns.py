graph [
  DateObtained "22/10/10"
  GeoLocation "Tokyo, Japan"
  GeoExtent "Metro"
  Network "T-lex"
  Provenance "Primary"
  Access 0
  Source "http://www.t-lex.net/"
  Version "1.0"
  DateType "Current"
  Type "REN"
  Backbone 1
  Commercial 0
  label "TLex"
  ToolsetVersion "0.3.34dev-20120328"
  Customer 0
  IX 1
  SourceGitVersion "e278b1b"
  DateModifier "="
  DateMonth "08"
  LastAccess "3/08/10"
  Layer "Layer 2"
  Creator "Topology Zoo Toolset"
  Developed 1
  Transit 1
  NetworkDate "2010_08"
  DateYear "2010"
  LastProcessed "2011_09_01"
  Testbed 0
  node [
    id 0
    label "Pacific NW Gigapop (Seattle, WA)"
    Internal 0
  ]
  node [
    id 1
    label "Future IEEAF Asian Extension"
    Internal 0
  ]
  node [
    id 2
    label "Cat 6500 AS23814"
    Internal 1
  ]
  node [
    id 3
    label "ONS-15454"
    Country "France"
    Longitude 1.92302
    Internal 1
    Latitude 49.41631
  ]
  node [
    id 4
    label "DR Data Reservoir"
    Internal 0
  ]
  node [
    id 5
    label "U-Tokyo akihabara"
    Internal 0
  ]
  node [
    id 6
    label "JGN2"
    Internal 0
  ]
  node [
    id 7
    label "APAN-JP AS7660"
    Internal 0
  ]
  node [
    id 8
    label "WIDE AS2500"
    Internal 0
  ]
  node [
    id 9
    label "ASCC/TW AS9264"
    Internal 0
  ]
  node [
    id 10
    label "BigIron 15000 AS23814"
    Internal 1
  ]
  node [
    id 11
    label "NetIron N140G AS23814"
    Internal 1
  ]
  edge [
    source 0
    target 3
    LinkType "OC-12"
    LinkLabel "OC-12"
  ]
  edge [
    source 0
    target 3
    LinkType "OC-192"
    LinkLabel "OC-192"
  ]
  edge [
    source 1
    target 3
    LinkType "OC-192"
    LinkLabel "OC-192 (Future)"
    LinkStatus "Future"
  ]
  edge [
    source 2
    target 11
    LinkSpeed "10"
    LinkNote "E"
    LinkLabel "10GE"
    LinkSpeedUnits "G"
    LinkSpeedRaw 10000000000.0
  ]
  edge [
    source 2
    target 3
    LinkLabel "WANPHY"
  ]
  edge [
    source 2
    target 3
    LinkType "OC-48"
    LinkLabel "OC-48"
  ]
  edge [
    source 3
    target 11
    LinkLabel "WANPHY"
  ]
  edge [
    source 3
    target 10
    LinkLabel "8*GbE"
  ]
  edge [
    source 3
    target 10
    id "e6"
  ]
  edge [
    source 4
    target 11
    id "e0"
  ]
  edge [
    source 5
    target 11
    id "e1"
  ]
  edge [
    source 6
    target 11
    id "e2"
  ]
  edge [
    source 7
    target 11
    id "e3"
  ]
  edge [
    source 8
    target 11
    id "e4"
  ]
  edge [
    source 9
    target 10
    id "e5"
  ]
  edge [
    source 10
    target 11
    id "e8"
  ]
]
