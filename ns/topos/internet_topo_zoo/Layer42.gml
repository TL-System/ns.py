graph [
  DateObtained "16/01/11"
  GeoLocation "USA"
  GeoExtent "Country"
  Network "Layer42"
  Provenance "Primary"
  Access 0
  Source "http://www.layer42.net/network/national.html"
  Version "1.0"
  Type "COM"
  DateType "Current"
  Backbone 1
  Commercial 0
  label "Layer42"
  ToolsetVersion "0.3.34dev-20120328"
  Customer 1
  IX 0
  SourceGitVersion "e278b1b"
  DateModifier "="
  DateMonth "01"
  LastAccess "16/01/11"
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
    label "San Francisco"
    Country "United States"
    Longitude -122.41942
    Internal 1
    Latitude 37.77493
  ]
  node [
    id 2
    label "Los Angeles"
    Country "United States"
    Longitude -118.24368
    Internal 1
    Latitude 34.05223
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
    label "New York City"
    Country "United States"
    Longitude -74.00597
    Internal 1
    Latitude 40.71427
  ]
  node [
    id 5
    label "Washington DC"
    Country "United States"
    Longitude -77.03637
    Internal 1
    Latitude 38.89511
  ]
  edge [
    source 0
    target 1
    id "e0"
  ]
  edge [
    source 1
    target 2
    id "e1"
  ]
  edge [
    source 1
    target 3
    id "e2"
  ]
  edge [
    source 1
    target 5
    id "e3"
  ]
  edge [
    source 3
    target 4
    id "e4"
  ]
  edge [
    source 3
    target 5
    id "e5"
  ]
  edge [
    source 4
    target 5
    id "e6"
  ]
]
