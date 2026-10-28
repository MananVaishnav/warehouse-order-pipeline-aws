variable "region" {
  type    = string
  default = "ap-south-1"
}

variable "project" {
  type    = string
  default = "warehouse"
}

variable "alert_email" {
  type        = string
  description = "Email that receives alarm and low-stock alerts"
}
