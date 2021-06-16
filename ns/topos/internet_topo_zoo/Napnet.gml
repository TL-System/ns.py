graph [
  DateObtained "14/01/11"
  GeoLocation "USA"
  GeoExtent "Country"
  Network "NapNet"
  Provenance "Secondary"
  Note "ATM only? No information"
  Source "http://www.nthelp.com/images/napnet.jpg"
  Version "1.0"
  Type "COM"
  DateType "Current"
  Backbone 0
  Commercial 0
  label "Napnet"
  ToolsetVersion "0.3.34dev-20120328"
  Customer 0
  IX 0
  SourceGitVersion "e278b1b"
  DateModifier "="
  DateMonth "01"
  LastAccess "14/01/11"
  Access 0
  Layer "IP"
  Creator "Topology Zoo Toolset"
  Developed 1
  Transit 0
  NetworkDate "2011_01"
  DateYear "2011"
  LastProcessed "2011_09_01"
  Testbed 0
  node [
    id 0
    label "Seattle"
    Country "United States"
    Longitude -122.33207
    Internal 1
    Latitude 47.60621
  ]
  node [
    id 1
    label "San Jose"
    Country "United States"
    Longitude -121.89496
    Internal 1
    Latitude 37.33939
  ]
  node [
    id 2
    label "Minneapolis"
    Country "United States"
    Longitude -93.26384
    Internal 1
    Latitude 44.97997
  ]
  node [
    id 3
    label "Chicago"
    Country "United States"
    Longitude -87.65005
    Internal 1
    Latitude 41.85003
  ]
  node [
    id 4
    label "Vienna"
    Country "United States"
    Longitude -77.26526
    Internal 1
    Latitude 38.90122
  ]
  node [
    id 5
    label "Dallas"
    Country "United States"
    Longitude -96.80667
    Internal 1
    Latitude 32.78306
  ]
  edge [
    source 0
    target 1
    id "e0"
  ]
  edge [
    source 0
    target 3
    id "e1"
  ]
  edge [
    source 1
    target 3
    id "e2"
  ]
  edge [
    source 1
    target 4
    LinkType "DS-3"
    LinkLabel "45 Mbps DS-3"
    LinkNote "45 Mbps "
  ]
  edge [
    source 2
    target 3
    id "e4"
  ]
  edge [
    source 3
    target 4
    id "e5"
  ]
  edge [
    source 3
    target 5
    id "e6"
  ]
]
