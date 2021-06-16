graph [
  DateObtained "22/10/10"
  GeoLocation "Singapore"
  GeoExtent "Country"
  Network "Singaren"
  Provenance "Primary"
  Access 0
  Source "http://www.singaren.net.sg/network.php"
  Version "1.0"
  Type "REN"
  DateType "Historic"
  Backbone 1
  Commercial 0
  label "Singaren"
  ToolsetVersion "0.3.34dev-20120328"
  Customer 0
  IX 1
  SourceGitVersion "e278b1b"
  DateModifier "="
  DateMonth 0
  LastAccess "3/08/10"
  Layer "IP"
  Creator "Topology Zoo Toolset"
  Developed 1
  Transit 0
  NetworkDate "2008"
  DateYear "2008"
  LastProcessed "2011_09_01"
  Testbed 0
  node [
    id 0
    label "NICT QGPOP APAN-JP Japan"
    Internal 0
  ]
  node [
    id 1
    label "AARNET"
    Internal 0
  ]
  node [
    id 2
    label "Academia Sinica Taiwan"
    Internal 0
  ]
  node [
    id 3
    label "NTU"
    Internal 1
  ]
  node [
    id 4
    label "Biopolis"
    Internal 1
  ]
  node [
    id 5
    label "Fusionopolis"
    Internal 1
  ]
  node [
    id 6
    label "NUS"
    Internal 1
  ]
  node [
    id 7
    label "Schools"
    Internal 1
  ]
  node [
    id 8
    label "SingAREN members"
    Internal 1
  ]
  node [
    id 9
    label "SingAREN-GIX"
    Internal 1
  ]
  node [
    id 10
    label "TEIN3"
    Internal 0
  ]
  edge [
    source 0
    target 9
    LinkType "STM-1"
    LinkLabel "IPLC STM-1"
    LinkNote "IPLC "
  ]
  edge [
    source 1
    target 9
    LinkType "Gige"
    LinkLabel "GigE"
  ]
  edge [
    source 2
    target 9
    LinkType "STM-1"
    LinkLabel "IPLC STM-1"
    LinkNote "IPLC "
  ]
  edge [
    source 3
    target 9
    LinkType "Gige"
    LinkLabel "GigE"
  ]
  edge [
    source 4
    target 9
    LinkType "Gige"
    LinkLabel "GigE"
  ]
  edge [
    source 5
    target 9
    LinkType "Gige"
    LinkLabel "GigE"
  ]
  edge [
    source 6
    target 9
    LinkType "Gige"
    LinkLabel "GigE"
  ]
  edge [
    source 7
    target 9
    id "e4"
  ]
  edge [
    source 8
    target 9
    LinkLabel "GigE/FE/ATM"
  ]
  edge [
    source 9
    target 10
    LinkType "Gige"
    LinkLabel "GigE"
  ]
]
