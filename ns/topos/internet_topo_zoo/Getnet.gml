graph [
  DateObtained "14/01/11"
  GeoLocation "USA"
  GeoExtent "Country"
  Network "GetNet"
  Provenance "Secondary"
  Note "No contemporary info. Was an ISP in 97 with reach but now appears to be Phoenix only? No buyout info"
  Source "http://www.nthelp.com/images/getnet.jpg"
  Version "1.0"
  Type "COM"
  DateType "Current"
  Backbone 0
  Commercial 0
  label "Getnet"
  ToolsetVersion "0.3.34dev-20120328"
  Customer 0
  IX 0
  SourceGitVersion "e278b1b"
  DateModifier "="
  DateMonth "01"
  LastAccess "14/01/11"
  Access 1
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
    label "Santa Clara"
    Country "United States"
    Longitude -121.95524
    Internal 1
    Latitude 37.35411
  ]
  node [
    id 2
    label "Phoenix"
    Country "United States"
    Longitude -112.07404
    Internal 1
    Latitude 33.44838
  ]
  node [
    id 3
    label "Tucson"
    Country "United States"
    Longitude -110.92648
    Internal 1
    Latitude 32.22174
  ]
  node [
    id 4
    label "Washington, DC"
    Country "United States"
    Longitude -77.03637
    Internal 1
    Latitude 38.89511
  ]
  node [
    id 5
    label "Baltimore"
    Country "United States"
    Longitude -76.61219
    Internal 1
    Latitude 39.29038
  ]
  node [
    id 6
    label "Pittsburgh"
    Country "United States"
    Longitude -79.99589
    Internal 1
    Latitude 40.44062
  ]
  edge [
    source 0
    target 1
    LinkType "DS-3"
    LinkLabel "45 Mbps DS-3"
    LinkNote "45 Mbps "
  ]
  edge [
    source 1
    target 2
    LinkType "DS-3"
    LinkLabel "45 Mbps DS-3"
    LinkNote "45 Mbps "
  ]
  edge [
    source 1
    target 4
    LinkType "DS-3"
    LinkLabel "45 Mbps DS-3"
    LinkNote "45 Mbps "
  ]
  edge [
    source 1
    target 6
    LinkType "DS-3"
    LinkLabel "45 Mbps DS-3"
    LinkNote "45 Mbps "
  ]
  edge [
    source 2
    target 3
    LinkType "DS-3"
    LinkLabel "45 Mbps DS-3"
    LinkNote "45 Mbps "
  ]
  edge [
    source 2
    target 4
    LinkType "DS-3"
    LinkLabel "45 Mbps DS-3"
    LinkNote "45 Mbps "
  ]
  edge [
    source 4
    target 5
    LinkType "DS-3"
    LinkLabel "45 Mbps DS-3"
    LinkNote "45 Mbps "
  ]
  edge [
    source 5
    target 6
    LinkType "DS-3"
    LinkLabel "45 Mbps DS-3"
    LinkNote "45 Mbps "
  ]
]
