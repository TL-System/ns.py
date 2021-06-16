graph [
  DateObtained "12/07/11"
  GeoLocation "UK"
  GeoExtent "Country"
  Network "Janet External"
  Provenance "Primary"
  Access 0
  Source "http://webarchive.ja.net/about/topology/workingwiththeworld.pdf"
  Version "1.0"
  Type "REN"
  DateType "Current"
  Backbone 1
  Commercial 0
  label "JanetExternal"
  ToolsetVersion "0.3.34dev-20120328"
  Customer 0
  IX 0
  SourceGitVersion "e278b1b"
  DateModifier "="
  DateMonth "07"
  LastAccess "12/07/11"
  Layer "IP"
  Creator "Topology Zoo Toolset"
  Developed 0
  Transit 0
  NetworkDate "2011_07"
  DateYear "2011"
  LastProcessed "2011_09_01"
  Testbed 0
  node [
    id 0
    label "HEAnet"
    Internal 0
  ]
  node [
    id 1
    label "Europe (GEANT2)"
    Internal 0
  ]
  node [
    id 2
    label "People's Republic of China"
    Internal 0
  ]
  node [
    id 3
    label "Japan (NII)"
    Internal 0
  ]
  node [
    id 4
    label "Belfast"
    Country "United Kingdom"
    Longitude -5.93333
    Internal 1
    Latitude 54.58333
  ]
  node [
    id 5
    label "JANET"
    Internal 1
  ]
  node [
    id 6
    label "US Research Networks ESnet"
    Internal 0
  ]
  node [
    id 7
    label "US Research Networks Abilene"
    Internal 0
  ]
  node [
    id 8
    label "LINX"
    Internal 0
  ]
  node [
    id 9
    label "UK ISPs"
    Internal 0
  ]
  node [
    id 10
    label "Private Peering with ISPs"
    Internal 0
  ]
  node [
    id 11
    label "Global Transit to the World"
    Internal 0
  ]
  edge [
    source 0
    target 4
    LinkLabel "< 2.5 Gbps"
  ]
  edge [
    source 1
    target 2
    LinkLabel "< 2.5 Gbps"
  ]
  edge [
    source 1
    target 3
    LinkLabel "< 2.5 Gbps"
  ]
  edge [
    source 1
    target 5
    LinkLabel "< 2.5 Gbps"
  ]
  edge [
    source 1
    target 6
    LinkLabel "< 2.5 Gbps"
  ]
  edge [
    source 1
    target 7
    LinkLabel "< 2.5 Gbps"
  ]
  edge [
    source 5
    target 8
    LinkLabel "< 2.5 Gbps"
  ]
  edge [
    source 5
    target 10
    LinkLabel "< 2.5 Gbps"
  ]
  edge [
    source 5
    target 11
    LinkLabel "< 2.5 Gbps"
  ]
  edge [
    source 8
    target 9
    LinkLabel "< 2.5 Gbps"
  ]
]
