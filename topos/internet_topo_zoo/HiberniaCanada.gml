graph [
  DateObtained "23/03/11"
  GeoLocation "Canada"
  GeoExtent "Country"
  Network "Hibernia Atlantic (Canada)"
  Provenance "Primary"
  Access 0
  Source "http://www.hiberniaatlantic.com/Canada_network.html"
  Version "1.0"
  Type "COM"
  DateType "Current"
  Backbone 1
  Commercial 0
  label "HiberniaCanada"
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
    label "New York"
    Country "Canada"
    Longitude -79.06627
    Internal 1
    Latitude 43.08342
    type "Yellow Node"
  ]
  node [
    id 1
    label "None"
    Internal 0
  ]
  node [
    id 2
    label "None"
    Internal 0
  ]
  node [
    id 3
    label "Moncton"
    Country "Canada"
    Longitude -64.80186
    Internal 1
    Latitude 46.11594
    type "Green Node"
  ]
  node [
    id 4
    label "None"
    hyperedge 1
    Internal 1
  ]
  node [
    id 5
    label "Edmundston"
    Country "Canada"
    Longitude -68.32512
    Internal 1
    Latitude 47.3737
    type "Green Node"
  ]
  node [
    id 6
    label "Quebec"
    Country "Canada"
    Longitude -71.21454
    Internal 1
    Latitude 46.81228
    type "Green Node"
  ]
  node [
    id 7
    label "Montreal"
    Country "Canada"
    Longitude -73.58781
    Internal 1
    Latitude 45.50884
    type "Green Node"
  ]
  node [
    id 8
    label "Toronto"
    Country "Canada"
    Longitude -79.4163
    Internal 1
    Latitude 43.70011
    type "Green Node"
  ]
  node [
    id 9
    label "Buffalo"
    Country "Canada"
    Longitude -108.48475
    Internal 1
    Latitude 55.85017
    type "Green Node"
  ]
  node [
    id 10
    label "Albany"
    Country "Canada"
    Longitude -63.64872
    Internal 1
    Latitude 46.28343
    type "Green Node"
  ]
  node [
    id 11
    label "Boston"
    Country "Canada"
    Longitude -121.44399
    Internal 1
    Latitude 49.87002
    type "Green Node"
  ]
  node [
    id 12
    label "Halifax"
    Country "Canada"
    Longitude -63.57333
    Internal 1
    Latitude 44.646
    type "Green Node"
  ]
  edge [
    source 0
    target 10
    LinkLabel "Green Link"
  ]
  edge [
    source 0
    target 11
    LinkLabel "Green Link"
  ]
  edge [
    source 1
    target 4
    LinkLabel "Blue Link"
  ]
  edge [
    source 2
    target 12
    LinkLabel "Blue Link"
  ]
  edge [
    source 3
    target 12
    LinkLabel "Green Link"
  ]
  edge [
    source 3
    target 5
    LinkLabel "Green Link"
  ]
  edge [
    source 4
    target 11
    LinkLabel "Blue Link"
  ]
  edge [
    source 4
    target 12
    LinkLabel "Blue Link"
  ]
  edge [
    source 5
    target 6
    LinkLabel "Green Link"
  ]
  edge [
    source 6
    target 7
    LinkLabel "Green Link"
  ]
  edge [
    source 7
    target 8
    LinkLabel "Green Link"
  ]
  edge [
    source 7
    target 10
    LinkLabel "Green Link"
  ]
  edge [
    source 8
    target 9
    LinkLabel "Green Link"
  ]
  edge [
    source 9
    target 10
    LinkLabel "Green Link"
  ]
]
