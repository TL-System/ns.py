graph [
  DateObtained "12/07/11"
  GeoLocation "Moldova"
  GeoExtent "Country"
  Network "Renam"
  Provenance "Primary"
  Note "Information unclear, only links between main towns recorded."
  Source "http://www.renam.md/index.php?option=com_content&task=view&id=10&Itemid=16"
  Version "1.0"
  Type "REN"
  DateType "Historic"
  Backbone 1
  Commercial 0
  label "Renam"
  ToolsetVersion "0.3.34dev-20120328"
  Customer 1
  IX 0
  SourceGitVersion "e278b1b"
  DateModifier "="
  DateMonth 0
  LastAccess "12/07/11"
  Access 0
  Layer "IP"
  Creator "Topology Zoo Toolset"
  Developed 0
  Transit 0
  NetworkDate "2007"
  DateYear "2007"
  LastProcessed "2011_09_01"
  Testbed 0
  node [
    id 0
    label "Chisinau"
    Country "Moldova"
    Longitude 28.8575
    Internal 1
    Latitude 47.00556
  ]
  node [
    id 1
    label "Balti"
    Country "Moldova"
    Longitude 27.92889
    Internal 1
    Latitude 47.76167
  ]
  node [
    id 2
    label "       Cahul"
    Country "Moldova"
    Longitude 28.19444
    Internal 1
    Latitude 45.9075
  ]
  node [
    id 3
    label "StarNet ISP"
    Internal 0
  ]
  node [
    id 4
    label "RoEduNet"
    Internal 0
  ]
  edge [
    source 0
    target 1
    LinkSpeed "8"
    LinkLabel "8 Mbps"
    LinkSpeedUnits "M"
    LinkSpeedRaw 8000000.0
  ]
  edge [
    source 0
    target 2
    LinkSpeed "128"
    LinkLabel "128 Kbps"
    LinkSpeedUnits "K"
    LinkSpeedRaw 128000.0
  ]
  edge [
    source 0
    target 3
    id "e2"
  ]
  edge [
    source 0
    target 4
    LinkSpeed "32"
    LinkLabel "32 Mbps"
    LinkSpeedUnits "M"
    LinkSpeedRaw 32000000.0
  ]
]
