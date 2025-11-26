import request from '@/utils/request'

export function login(username, password) {
  return request({
    url: '/auth/login/',
    method: 'post',
    data: {
      username,
      password
    }
  })
}

export function getUserProfile() {
  return request({
    url: '/auth/users/profile/',
    method: 'get'
  })
}

export function updateProfile(data) {
  return request({
    url: '/auth/users/update_profile/',
    method: 'put',
    data
  })
}

export function changePassword(data) {
  return request({
    url: '/auth/users/change_password/',
    method: 'post',
    data
  })
}

export function getUsers(params) {
  return request({
    url: '/auth/users/',
    method: 'get',
    params
  })
}

export function createUser(data) {
  return request({
    url: '/auth/users/',
    method: 'post',
    data
  })
}

export function updateUser(id, data) {
  return request({
    url: `/auth/users/${id}/`,
    method: 'put',
    data
  })
}

export function deleteUser(id) {
  return request({
    url: `/auth/users/${id}/`,
    method: 'delete'
  })
}

export function getRoles(params) {
  return request({
    url: '/auth/roles/',
    method: 'get',
    params
  })
}

export function getDepartments(params) {
  return request({
    url: '/auth/departments/',
    method: 'get',
    params
  })
}

export function getDepartmentTree() {
  return request({
    url: '/auth/departments/tree/',
    method: 'get'
  })
}

