graph [
  DateObtained "23/03/11"
  GeoLocation "Ireland"
  GeoExtent "Country"
  Network "Hibernia Atlantic (Ireland)"
  Provenance "Primary"
  Access 0
  Source "http://www.hiberniaatlantic.com/Ireland_network.html"
  Version "1.0"
  Type "COM"
  DateType "Current"
  Backbone 1
  Commercial 0
  label "HiberniaIreland"
  ToolsetVersion "0.3.34dev-20120328"
  Customer 0
  IX 0
  SourceGitVersion "e278b1b"
  DateModifier "="
  DateMonth "03"
  LastAccess "23/03/11"
  Layer "IP"
  Creator "Topology Zoo Toolset"
  Developed 0
  Transit 1
  NetworkDate "2011_03"
  DateYear "2011"
  LastProcessed "2011_09_01"
  Testbed 0
  node [
    id 0
    label "Dublin"
    Country "Ireland"
    Longitude -6.26719
    Internal 1
    Latitude 53.34399
    type "Large Node"
  ]
  node [
    id 1
    label "Galway"
    Country "Ireland"
    Longitude -9.04889
    Internal 1
    Latitude 53.27194
    type "Small Node"
  ]
  node [
    id 2
    label "Limerick"
    Country "Ireland"
    Longitude -8.62306
    Internal 1
    Latitude 52.66472
    type "Small Node"
  ]
  node [
    id 3
    label "Cork"
    Country "Ireland"
    Longitude -8.49583
    Internal 1
    Latitude 51.89861
    type "Small Node"
  ]
  node [
    id 4
    label "Waterford"
    Country "Ireland"
    Longitude -7.11194
    Internal 1
    Latitude 52.25833
    type "Small Node"
  ]
  node [
    id 5
    label "Portlaioise"
    Country "Ireland"
    Longitude -7.29979
    Internal 1
    Latitude 53.03441
    type "Small Node"
  ]
  node [
    id 6
    label "None"
    Internal 0
  ]
  node [
    id 7
    label "None"
    Internal 0
  ]
  edge [
    source 0
    target 4
    LinkLabel "Blue Link"
  ]
  edge [
    source 0
    target 5
    LinkLabel "Blue Link"
  ]
  edge [
    source 0
    target 6
    LinkLabel "Green Link"
  ]
  edge [
    source 0
    target 7
    LinkLabel "Green Link"
  ]
  edge [
    source 1
    target 2
    LinkLabel "Blue Link"
  ]
  edge [
    source 2
    target 3
    LinkLabel "Blue Link"
  ]
  edge [
    source 2
    target 5
    LinkLabel "Blue Link"
  ]
  edge [
    source 3
    target 4
    LinkLabel "Blue Link"
  ]
]
