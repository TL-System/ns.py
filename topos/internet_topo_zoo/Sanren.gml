graph [
  DateObtained "3/02/11"
  GeoLocation "South Africa"
  GeoExtent "Country"
  Network "Sanren"
  Provenance "Primary"
  Note "Also http://www.sanren.ac.za/design/backbone/ used"
  Source "http://www.sanren.ac.za/"
  Version "1.0"
  Type "REN"
  DateType "Current"
  Backbone 1
  Commercial 0
  label "Sanren"
  ToolsetVersion "0.3.34dev-20120328"
  Customer 0
  IX 0
  SourceGitVersion "e278b1b"
  DateModifier "="
  DateMonth "03"
  LastAccess "6/03/11"
  Access 0
  Layer "IP"
  Creator "Topology Zoo Toolset"
  Developed 0
  Transit 0
  NetworkDate "2011_03"
  DateYear "2011"
  LastProcessed "2011_09_01"
  Testbed 0
  node [
    id 0
    label "Johannesburg"
    Country "South Africa"
    Longitude 28.04363
    Internal 1
    Latitude -26.20227
  ]
  node [
    id 1
    label "Pretoria"
    Country "South Africa"
    Longitude 28.18783
    Internal 1
    Latitude -25.74486
  ]
  node [
    id 2
    label "Durban"
    Country "South Africa"
    Longitude 31.01667
    Internal 1
    Latitude -29.85
  ]
  node [
    id 3
    label "Bloemfontein"
    Country "South Africa"
    Longitude 26.2
    Internal 1
    Latitude -29.13333
  ]
  node [
    id 4
    label "East London"
    Country "South Africa"
    Longitude 27.91162
    Internal 1
    Latitude -33.01529
  ]
  node [
    id 5
    label "Port Elizabeth"
    Country "South Africa"
    Longitude 25.58333
    Internal 1
    Latitude -33.96667
  ]
  node [
    id 6
    label "Cape Town"
    Country "South Africa"
    Longitude 18.41667
    Internal 1
    Latitude -33.91667
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
    target 2
    id "e2"
  ]
  edge [
    source 2
    target 4
    id "e3"
  ]
  edge [
    source 3
    target 6
    id "e4"
  ]
  edge [
    source 4
    target 5
    id "e5"
  ]
  edge [
    source 5
    target 6
    id "e6"
  ]
]
